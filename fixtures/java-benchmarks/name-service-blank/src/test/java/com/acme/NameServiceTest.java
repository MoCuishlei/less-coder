package com.acme;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class NameServiceTest {
    @Test
    void shouldUppercaseTrimmedName() {
        NameService service = new NameService();
        assertEquals("ALICE", service.normalizeName("  alice "));
    }

    @Test
    void shouldReturnUnknownForBlank() {
        NameService service = new NameService();
        assertEquals("UNKNOWN", service.normalizeName("   "));
    }
}
