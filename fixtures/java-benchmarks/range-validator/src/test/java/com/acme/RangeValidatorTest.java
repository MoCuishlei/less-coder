package com.acme;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RangeValidatorTest {
    @Test
    void shouldAcceptMiddleValue() {
        RangeValidator validator = new RangeValidator();
        assertTrue(validator.isWithinRange(5, 1, 10));
    }

    @Test
    void shouldIncludeBoundaryValues() {
        RangeValidator validator = new RangeValidator();
        assertTrue(validator.isWithinRange(1, 1, 10));
    }

    @Test
    void shouldRejectValueAboveMax() {
        RangeValidator validator = new RangeValidator();
        assertFalse(validator.isWithinRange(11, 1, 10));
    }
}
