package com.portfolio.cow.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtUtilsTest {

    private JwtUtils jwtUtils(long expireMinutes) {
        JwtUtils utils = new JwtUtils();
        // HS256 要求密钥 ≥ 256bit
        ReflectionTestUtils.setField(utils, "secret",
                "cow-admin-jwt-secret-for-unit-test-0123456789abcdef");
        ReflectionTestUtils.setField(utils, "expireMinutes", expireMinutes);
        return utils;
    }

    @Test
    void issueAndParseRoundTrip() {
        JwtUtils utils = jwtUtils(120);
        String token = utils.createToken(42L, "admin");
        Claims claims = utils.parse(token);
        assertEquals("admin", claims.getSubject());
        assertEquals(42, claims.get("uid", Integer.class));
        assertEquals("admin", utils.getUsername(token));
    }

    @Test
    void expiredTokenRejected() {
        JwtUtils utils = jwtUtils(-10);
        String token = utils.createToken(42L, "admin");
        assertThrows(ExpiredJwtException.class, () -> utils.parse(token));
    }

    @Test
    void tamperedSignatureRejected() {
        JwtUtils utils = jwtUtils(120);
        String token = utils.createToken(42L, "admin");
        // 篡改签名段最后一个字符
        char last = token.charAt(token.length() - 1);
        String tampered = token.substring(0, token.length() - 1) + (last == 'A' ? 'B' : 'A');
        assertThrows(JwtException.class, () -> utils.parse(tampered));
    }
}
