package com.portfolio.cow.modules.system.controller;

import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.system.dto.LoginRequest;
import com.portfolio.cow.security.JwtUtils;
import com.portfolio.cow.security.LoginUser;
import com.portfolio.cow.security.UserDetailsServiceImpl;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserDetailsServiceImpl userDetailsService;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtils jwtUtils;

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@Valid @RequestBody LoginRequest request) {
        LoginUser user = (LoginUser) userDetailsService.loadUserByUsername(request.getUsername());
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BizException(ResultCode.UNAUTHORIZED.getCode(), "用户名或密码错误");
        }
        String token = jwtUtils.createToken(user.getId(), user.getUsername());
        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("username", user.getUsername());
        data.put("nickname", user.getNickname());
        return Result.ok(data);
    }

    @GetMapping("/profile")
    public Result<Map<String, Object>> profile() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        if (!(principal instanceof LoginUser user)) {
            throw new BizException(ResultCode.UNAUTHORIZED);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("id", user.getId());
        data.put("username", user.getUsername());
        data.put("nickname", user.getNickname());
        data.put("roles", user.getRoles());
        data.put("perms", user.getPerms());
        return Result.ok(data);
    }

    @PostMapping("/logout")
    public Result<Void> logout() {
        SecurityContextHolder.clearContext();
        return Result.ok();
    }
}
