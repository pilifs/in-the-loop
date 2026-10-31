package net.terminalvalue.crosscut.security;

/**
 * The time checks of a JWT validator ({@code nbf} and {@code exp}, RFC 7519 section 4.1) with the clock skew
 * tolerance of Spring Security's {@code JwtTimestampValidator}: a token is accepted up to {@code skewSeconds}
 * before its not-before time and up to {@code skewSeconds} after its expiry, because the issuer's clock and the
 * resource server's clock are never quite the same.
 */
public final class JwtTimestamps {

    private JwtTimestamps() {}

    /** Whether a token with the given {@code nbf} and {@code exp} is valid at {@code nowSeconds}, with the skew. */
    public static boolean valid(long nowSeconds, long notBefore, long expiresAt, long skewSeconds) {
        if (skewSeconds < 0) {
            throw new IllegalArgumentException("the clock skew tolerance is not negative");
        }
        return nowSeconds >= notBefore - skewSeconds && nowSeconds < expiresAt + skewSeconds;
    }
}
