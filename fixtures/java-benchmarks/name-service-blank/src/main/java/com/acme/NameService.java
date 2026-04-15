package com.acme;

public class NameService {
    public String normalizeName(String input) {
        if (input == null) {
            return "UNKNOWN";
        }
        return input.trim().toUpperCase();
    }
}
