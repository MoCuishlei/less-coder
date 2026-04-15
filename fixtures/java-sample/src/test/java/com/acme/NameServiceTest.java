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
    void shouldReturnUnknownForNull() {
        NameService service = new NameService();
        assertEquals("UNKNOWN", service.normalizeName(null));
    }

    @Test
    void shouldReturnUnknownForBlank() {
        NameService service = new NameService();
        // This test should currently fail and serve as the L1 repair baseline.
        assertEquals("UNKNOWN", service.normalizeName("   "));
    }
}
