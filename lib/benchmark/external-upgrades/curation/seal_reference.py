"""Sign, encrypt and independently verify a curator packet outside the checkout."""

import argparse
import hashlib
import json
import os
import re
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


MAGIC = b"ITU-REF\x01"
SIGNATURE_CONTEXT = b"in-the-loop/external-upgrades/reference/v1\x00"
CHUNK = 1024 * 1024
NONCE_SIZE = 12
TAG_SIZE = 16
SIGNATURE_SIZE = 64


def outside_checkout(path):
    path = path.resolve()
    if any((p / "llm-dlc" / "tools" / "sync.py").is_file() for p in (path, *path.parents)):
        raise ValueError("custodian material belongs outside a checkout")
    return path


@contextmanager
def publish_once(output):
    """Expose the completed result atomically and refuse to replace an earlier one."""
    output = outside_checkout(output)
    with tempfile.NamedTemporaryFile(dir=output.parent) as staged:
        yield staged
        staged.flush()
        os.fsync(staged.fileno())
        os.link(staged.name, output)


def packet_label(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("a short neutral packet ID is required")
    return value.encode("ascii")


def pack(folder, out):
    if not folder.is_dir():
        raise ValueError("packet folder required")
    with tarfile.open(fileobj=out, mode="w:gz", dereference=True) as archive:
        count = 0
        for item in sorted(folder.rglob("*")):
            if item.is_symlink():
                raise ValueError("copy selected regular files into the curator packet")
            if item.is_file():
                archive.add(item, arcname=item.relative_to(folder), recursive=False)
                count += 1
            elif not item.is_dir():
                raise ValueError("unexpected nonregular packet entry")
        if not count:
            raise ValueError("empty packet")
    out.seek(0)


def raw_key(path):
    value = outside_checkout(path).read_bytes()
    if len(value) != 32:
        raise ValueError("expected a 32-byte key")
    return value


def public_bytes(commitment):
    value = json.loads(commitment.read_bytes())["signer_ed25519_raw_hex"]
    key = bytes.fromhex(value)
    if len(key) != 32:
        raise ValueError("invalid pinned public key")
    return key


def seal(args):
    folder = outside_checkout(args.folder)
    output = outside_checkout(args.output)
    if output.is_relative_to(folder):
        raise ValueError("packet output belongs outside its inputs")
    signer = Ed25519PrivateKey.from_private_bytes(raw_key(args.signing_key))
    signer_pub = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    if signer_pub != public_bytes(args.commitment):
        raise ValueError("signing key differs from the public commitment")
    if any(k.resolve().is_relative_to(folder) for k in (args.signing_key, args.encryption_key)):
        raise ValueError("custody keys belong outside the packet")
    label = packet_label(args.packet_id)
    nonce = os.urandom(NONCE_SIZE)
    header = MAGIC + bytes([len(label)]) + label + nonce
    cipher = Cipher(algorithms.AES(raw_key(args.encryption_key)), modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(header)
    digest = hashlib.sha256(header)
    with tempfile.TemporaryFile(dir=output.parent) as archive:
        pack(folder, archive)
        with publish_once(output) as out:
            out.write(header)
            while block := archive.read(CHUNK):
                encrypted = cipher.update(block)
                out.write(encrypted)
                digest.update(encrypted)
            tail = cipher.finalize() + cipher.tag
            out.write(tail)
            digest.update(tail)
            signature = signer.sign(SIGNATURE_CONTEXT + digest.digest())
            out.write(signature)
    return receipt(label, digest, signature)


def receipt(label, digest, signature):
    return {
        "packet_id": label.decode("ascii"),
        "signed_envelope_sha256": digest.hexdigest(),
        "ed25519_signature": signature.hex(),
    }


def verify_packet(packet, commitment):
    """Verify the public signature before the encrypted archive is opened."""
    total = os.fstat(packet.fileno()).st_size
    if packet.read(len(MAGIC)) != MAGIC:
        raise ValueError("unknown packet format")
    size = packet.read(1)
    if not size:
        raise ValueError("truncated header")
    label = packet.read(size[0])
    packet_label(label.decode("ascii"))
    nonce = packet.read(NONCE_SIZE)
    header = MAGIC + size + label + nonce
    encrypted_length = total - len(header) - TAG_SIZE - SIGNATURE_SIZE
    if len(nonce) != NONCE_SIZE or encrypted_length <= 0:
        raise ValueError("truncated packet")
    digest = hashlib.sha256(header)
    remaining = encrypted_length + TAG_SIZE
    while remaining:
        block = packet.read(min(remaining, CHUNK))
        if not block:
            raise ValueError("truncated packet")
        digest.update(block)
        remaining -= len(block)
    signature = packet.read(SIGNATURE_SIZE)
    Ed25519PublicKey.from_public_bytes(public_bytes(commitment)).verify(
        signature, SIGNATURE_CONTEXT + digest.digest()
    )
    return receipt(label, digest, signature), header, nonce, encrypted_length


def read_packet(args):
    with args.packet.open("rb") as packet:
        result, header, nonce, length = verify_packet(packet, args.commitment)
        if args.command == "verify":
            return result
        packet.seek(len(header) + length)
        tag = packet.read(TAG_SIZE)
        cipher = Cipher(algorithms.AES(raw_key(args.encryption_key)), modes.GCM(nonce, tag)).decryptor()
        cipher.authenticate_additional_data(header)
        packet.seek(len(header))
        with publish_once(args.output) as out:
            while length:
                block = packet.read(min(length, CHUNK))
                if not block:
                    raise ValueError("truncated packet")
                out.write(cipher.update(block))
                length -= len(block)
            out.write(cipher.finalize())
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("seal", help="seal regular files in a private packet folder")
    write.add_argument("packet_id", help="neutral ID independent of the case stratum")
    write.add_argument("folder", type=Path)
    write.add_argument("output", type=Path)
    write.add_argument("--signing-key", required=True, type=Path)
    verify = commands.add_parser("verify", help="verify the encrypted packet with its public key")
    decrypt = commands.add_parser("open", help="verify and restore the private tar.gz archive")
    for cmd in (verify, decrypt):
        cmd.add_argument("packet", type=Path)
    decrypt.add_argument("output", type=Path)
    for cmd in (write, decrypt):
        cmd.add_argument("--encryption-key", required=True, type=Path)
    for cmd in (write, verify, decrypt):
        cmd.add_argument("--commitment", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = seal(args) if args.command == "seal" else read_packet(args)
    except (OSError, ValueError, KeyError, InvalidTag, InvalidSignature, tarfile.TarError):
        parser.exit(1, "Packet operation failed. Check inputs, custody keys and output location.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
