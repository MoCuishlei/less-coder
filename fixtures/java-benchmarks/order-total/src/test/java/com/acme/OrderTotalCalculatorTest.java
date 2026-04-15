package com.acme;

import org.junit.jupiter.api.Test;

import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertEquals;

class OrderTotalCalculatorTest {
    @Test
    void shouldSumAllItems() {
        OrderTotalCalculator calculator = new OrderTotalCalculator();
        assertEquals(60, calculator.total(Arrays.asList(10, 20, 30)));
    }

    @Test
    void shouldReturnZeroForEmptyOrder() {
        OrderTotalCalculator calculator = new OrderTotalCalculator();
        assertEquals(0, calculator.total(Arrays.asList()));
    }
}
