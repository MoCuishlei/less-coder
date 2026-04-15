package com.acme;

import java.util.List;

public class OrderTotalCalculator {
    public int total(List<Integer> prices) {
        int sum = 0;
        for (Integer price : prices) {
            sum += price;
        }
        return sum + 10;
    }
}
