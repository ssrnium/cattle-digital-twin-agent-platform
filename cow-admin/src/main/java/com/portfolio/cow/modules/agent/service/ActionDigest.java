package com.portfolio.cow.modules.agent.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Map;

/**
 * 写操作参数摘要：审批时登记、执行时重算比对，防止"批准后篡改参数"。
 * 规范化口径（两侧必须一致）：固定 6 个键 type/cow_id/device_id/source_event_id/priority/description，
 * null 归一为 ""，priority 空白归一为 "NORMAL"，按 "key=value" 逐行拼接后取 SHA-256 hex。
 */
public final class ActionDigest {

    private ActionDigest() {
    }

    /** 工具入参（snake_case）→ 摘要 */
    public static String ofToolParams(Map<String, Object> params) {
        Map<String, Object> p = params == null ? Map.of() : params;
        return of(str(p.get("type")), str(p.get("cow_id")), str(p.get("device_id")),
                str(p.get("source_event_id")), str(p.get("priority")), str(p.get("description")));
    }

    public static String of(String type, String cowId, String deviceId,
                            String sourceEventId, String priority, String description) {
        String canonical = "type=" + n(type)
                + "\ncow_id=" + n(cowId)
                + "\ndevice_id=" + n(deviceId)
                + "\nsource_event_id=" + n(sourceEventId)
                + "\npriority=" + (priority == null || priority.isBlank() ? "NORMAL" : priority)
                + "\ndescription=" + n(description);
        return sha256Hex(canonical);
    }

    private static String str(Object o) {
        return o == null ? "" : String.valueOf(o);
    }

    private static String n(String s) {
        return s == null ? "" : s;
    }

    private static String sha256Hex(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                sb.append(Character.forDigit((b >> 4) & 0xF, 16));
                sb.append(Character.forDigit(b & 0xF, 16));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
