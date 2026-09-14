package com.portfolio.cow.modules.agent.service;

import com.portfolio.cow.common.BizException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.Map;

/**
 * cow-agent（FastAPI + BearCode 牧场智能体）HTTP 客户端。
 * read 超时 150s：覆盖写操作确认 park 的 120s 等待窗口。
 */
@Component
public class AgentServiceClient {

    private final RestClient restClient;

    public AgentServiceClient(@Value("${agent.base-url}") String baseUrl) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(150_000);
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .build();
    }

    public Map<String, Object> chat(Map<String, Object> payload) {
        return post("/api/v1/agent/chat", payload);
    }

    public Map<String, Object> confirm(Map<String, Object> payload) {
        return post("/api/v1/agent/confirm", payload);
    }

    public Map<String, Object> sessions() {
        try {
            return restClient.get()
                    .uri("/api/v1/agent/sessions")
                    .retrieve()
                    .body(new ParameterizedTypeReference<Map<String, Object>>() {
                    });
        } catch (RestClientException e) {
            throw new BizException(502, "cow-agent 调用失败: " + e.getMessage());
        }
    }

    private Map<String, Object> post(String path, Map<String, Object> payload) {
        try {
            return restClient.post()
                    .uri(path)
                    .body(payload)
                    .retrieve()
                    .body(new ParameterizedTypeReference<Map<String, Object>>() {
                    });
        } catch (RestClientException e) {
            throw new BizException(502, "cow-agent 调用失败: " + e.getMessage());
        }
    }
}
