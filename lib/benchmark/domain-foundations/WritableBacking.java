package foundation;

import org.apache.hadoop.io.BytesWritable;

public final class WritableBacking {
    public static boolean shrink(byte[] bytes, int length) {
        byte[] saved = new byte[bytes.length];
        for (int i = 0; i < bytes.length; i++) saved[i] = bytes[i];
        BytesWritable writable = new BytesWritable(bytes);
        writable.setSize(length);
        if (writable.getLength() != length || writable.getCapacity() != saved.length || writable.getBytes() != bytes)
            return false;
        for (int i = 0; i < saved.length; i++) if (bytes[i] != saved[i]) return false;
        return true;
    }

    public static boolean growthChangesBacking() {
        byte[] bytes = {77};
        BytesWritable writable = new BytesWritable(bytes);
        writable.setSize(3);
        return writable.getBytes() != bytes && writable.getLength() == 3 && writable.getBytes()[0] == 77;
    }

    public static void main(String[] args) {
        for (int n = 0; n <= 6; n++) {
            byte[] bytes = new byte[n];
            for (int i = 0; i < n; i++) bytes[i] = (byte)(i * 37 - 128);
            for (int length = 0; length <= n; length++) if (!shrink(bytes, length)) throw new AssertionError();
        }
        if (!growthChangesBacking()) throw new AssertionError();
        System.out.println("held");
    }
}
