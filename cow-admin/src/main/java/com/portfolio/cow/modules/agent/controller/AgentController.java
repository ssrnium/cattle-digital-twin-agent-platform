package com.portfolio.cow.modules.agent.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.modules.agent.dto.AgentChatRequest;
import com.portfolio.cow.modules.agent.dto.AgentConfirmRequest;
import com.portfolio.cow.modules.agent.entity.AgentMessage;
import com.portfolio.cow.modules.agent.entity.AgentSession;
import com.portfolio.cow.modules.agent.mapper.AgentMessageMapper;
import com.portfolio.cow.modules.agent.mapper.AgentSessionMapper;
import com.portfolio.cow.modules.agent.service.AgentServiceClient;
import com.portfolio.cow.modules.system.annotation.OperLog;
import com.portfolio.cow.security.LoginUser;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 牧场智能体代理入口：鉴权（agent:chat）+ 会话/消息审计落库 + 转发 cow-agent。
 * 写操作确认（confirm）不 park 在这里——cow-agent 内部 await Future，本控制器只转发审批结果。
 */
@RestController
@RequestMapping("/api/v1/agent")
@RequiredArgsConstructor
public class AgentController {

    private final AgentServiceClient agentServiceClient;
    private final AgentSessionMapper sessionMapper;
    private final AgentMessageMapper messageMapper;

    @PostMapping("/chat")
    @PreAuthorize("hasAnyAuthority('agent:chat', '*')")
    @OperLog(title = "AI助手对话")
    public Result<Map<String, Object>> chat(@Valid @RequestBody AgentChatRequest request) {
        String username = currentUsername();
        AgentSession session = upsertSession(request.getSessionId(), username);
        saveMessage(session.getSessionId(), AgentMessage.ROLE_USER, request.getMessage(), null, null);

        Map<String, Object> payload = new HashMap<>();
        payload.put("session_id", session.getSessionId());
        payload.put("message", request.getMessage());
        Map<String, Object> resp = agentServiceClient.chat(payload);

        Integer tokensInput = null;
        Integer tokensOutput = null;
        Object tokens = resp.get("tokens");
        if (tokens instanceof Map<?, ?> t) {
            tokensInput = toInt(t.get("input"));
            tokensOutput = toInt(t.get("output"));
        }
        saveMessage(session.getSessionId(), AgentMessage.ROLE_ASSISTANT,
                String.valueOf(resp.get("reply")), tokensInput, tokensOutput);
        touch(session);
        return Result.ok(resp);
    }

    @PostMapping("/confirm")
    @PreAuthorize("hasAnyAuthority('agent:chat', '*')")
    @OperLog(title = "AI助手写操作审批")
    public Result<Map<String, Object>> confirm(@Valid @RequestBody AgentConfirmRequest request) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("session_id", request.getSessionId());
        payload.put("approved", request.getApproved());
        return Result.ok(agentServiceClient.confirm(payload));
    }

    /** 会话列表（含待确认写操作），供前端轮询弹审批框 */
    @GetMapping("/sessions")
    @PreAuthorize("hasAnyAuthority('agent:chat', '*')")
    public Result<Map<String, Object>> sessions() {
        return Result.ok(agentServiceClient.sessions());
    }

    private AgentSession upsertSession(String sessionId, String username) {
        if (sessionId != null && !sessionId.isBlank()) {
            AgentSession existing = sessionMapper.selectOne(new LambdaQueryWrapper<AgentSession>()
                    .eq(AgentSession::getSessionId, sessionId));
            if (existing != null) {
                return existing;
            }
        }
        AgentSession session = new AgentSession();
        // sessionId 为空时先占位，cow-agent 会生成真实 session_id 返回；
        // 但审计表 uk 约束要求唯一，故用请求侧 UUID 预生成并传给 cow-agent
        session.setSessionId(sessionId == null || sessionId.isBlank()
                ? java.util.UUID.randomUUID().toString().replace("-", "").substring(0, 12)
                : sessionId);
        session.setUsername(username);
        session.setCreateTime(LocalDateTime.now());
        session.setLastActiveTime(LocalDateTime.now());
        sessionMapper.insert(session);
        return session;
    }

    private void saveMessage(String sessionId, String role, String content,
                             Integer tokensInput, Integer tokensOutput) {
        AgentMessage message = new AgentMessage();
        message.setSessionId(sessionId);
        message.setRole(role);
        message.setContent(content);
        message.setTokensInput(tokensInput);
        message.setTokensOutput(tokensOutput);
        message.setCreateTime(LocalDateTime.now());
        messageMapper.insert(message);
    }

    private void touch(AgentSession session) {
        session.setLastActiveTime(LocalDateTime.now());
        sessionMapper.updateById(session);
    }

    private String currentUsername() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return principal instanceof LoginUser u ? u.getUsername() : "unknown";
    }

    private Integer toInt(Object o) {
        return o == null ? null : Integer.valueOf(String.valueOf(o));
    }
}
