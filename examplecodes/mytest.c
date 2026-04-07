#include <stdio.h>
#include <string.h>

/**
 * Calculates the sum of two integers.
 */
int add(int a, int b) {
    return a + b;
}

void greet(char* name) {
    printf("Hello, %s!\n", name);
}

int main() {
    printf("Sum: %d\n", add(5, 3));
    greet("World");
    return 0;
}