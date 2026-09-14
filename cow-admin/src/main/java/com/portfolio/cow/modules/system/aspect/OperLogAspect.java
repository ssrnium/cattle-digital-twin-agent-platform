package com.portfolio.cow.modules.system.aspect;

import com.portfolio.cow.modules.system.annotation.OperLog;
import com.portfolio.cow.modules.system.entity.SysOperationLog;
import com.portfolio.cow.modules.system.mapper.SysOperationLogMapper;
import com.portfolio.cow.security.LoginUser;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.time.LocalDateTime;
import java.util.Arrays;

@Slf4j
@Aspect
@Component
@RequiredArgsConstructor
public class OperLogAspect {

    private final SysOperationLogMapper operationLogMapper;

    @Around("@annotation(operLog)")
    public Object around(ProceedingJoinPoint point, OperLog operLog) throws Throwable {
        SysOperationLog logEntity = new SysOperationLog();
        logEntity.setTitle(operLog.title());
        logEntity.setMethod(point.getSignature().toShortString());
        logEntity.setOperateTime(LocalDateTime.now());

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof LoginUser loginUser) {
            logEntity.setUsername(loginUser.getUsername());
        }
        ServletRequestAttributes attrs =
                (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attrs != null) {
            HttpServletRequest request = attrs.getRequest();
            logEntity.setRequestUri(request.getRequestURI());
            logEntity.setRequestIp(request.getRemoteAddr());
        }
        try {
            logEntity.setParams(truncate(Arrays.toString(point.getArgs())));
        } catch (Exception ignored) {
        }

        try {
            Object result = point.proceed();
            logEntity.setStatus("SUCCESS");
            return result;
        } catch (Throwable e) {
            logEntity.setStatus("FAIL");
            logEntity.setErrorMsg(truncate(e.getMessage()));
            throw e;
        } finally {
            try {
                operationLogMapper.insert(logEntity);
            } catch (Exception e) {
                log.warn("write operation log failed: {}", e.getMessage());
            }
        }
    }

    private String truncate(String s) {
        if (s == null) {
            return null;
        }
        return s.length() > 2000 ? s.substring(0, 2000) : s;
    }
}
