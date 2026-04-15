package com.acme;

public class RangeValidator {
    public boolean isWithinRange(int value, int min, int max) {
        return value > min && value < max;
    }
}
