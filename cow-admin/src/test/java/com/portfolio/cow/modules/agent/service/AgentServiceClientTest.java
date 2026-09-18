package com.portfolio.cow.modules.agent.service;

import com.portfolio.cow.common.BizException;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * AgentServiceClient 内部自建 RestClient，无法用 Mockito 注入；
 * 改用 JDK 内置 HttpServer 起本地桩，验证真实 HTTP 行为。
 */
class AgentServiceClientTest {

    private HttpServer server;
    private AgentServiceClient client;
    private final AtomicReference<String> lastPath = new AtomicReference<>();
    private final AtomicReference<String> lastBody = new AtomicReference<>();

    private void startServer(int status, String responseBody) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            lastPath.set(exchange.getRequestURI().getPath());
            lastBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] bytes = responseBody.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });
        server.start();
        client = new AgentServiceClient("http://127.0.0.1:" + server.getAddress().getPort());
    }

    @AfterEach
    void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void chatPostsToAgentChatApi() throws IOException {
        startServer(200, "{\"reply\":\"ok\",\"tokens\":{\"input\":10,\"output\":5}}");
        Map<String, Object> resp = client.chat(Map.of("session_id", "s1", "message", "hi"));
        assertEquals("/api/v1/agent/chat", lastPath.get());
        assertTrue(lastBody.get().contains("\"session_id\":\"s1\""));
        assertEquals("ok", resp.get("reply"));
    }

    @Test
    void confirmPostsApprovalToConfirmApi() throws IOException {
        startServer(200, "{\"status\":\"executed\"}");
        Map<String, Object> resp = client.confirm(Map.of("session_id", "s1", "approved", true));
        assertEquals("/api/v1/agent/confirm", lastPath.get());
        assertTrue(lastBody.get().contains("\"approved\":true"));
        assertEquals("executed", resp.get("status"));
    }

    @Test
    void agentDownMapsTo502BizException() throws IOException {
        startServer(500, "Internal Server Error");
        BizException e = assertThrows(BizException.class,
                () -> client.chat(Map.of("session_id", "s1", "message", "hi")));
        assertEquals(502, e.getCode());
    }
}
