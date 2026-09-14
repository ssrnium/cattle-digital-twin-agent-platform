package com.portfolio.cow.modules.event.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class IngestResponse {

    private String eventId;
    /** true = 重复事件被幂等拦截，未落库未告警 */
    private boolean duplicated;
    private String message;

    public static IngestResponse accepted(String eventId) {
        return new IngestResponse(eventId, false, "accepted");
    }

    public static IngestResponse duplicated(String eventId) {
        return new IngestResponse(eventId, true, "duplicated event_id, ignored");
    }
}
