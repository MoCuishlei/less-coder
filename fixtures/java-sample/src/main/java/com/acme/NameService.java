package com.acme;

public class NameService {
    public String normalizeName(String input) {
        // Known bug for L1 fixture: blank strings are not treated as invalid.
        if (input == null || input.trim().isEmpty()) {
            return "UNKNOWN";
        }
        return input.trim().toUpperCase();
    }
}
