public class Test1 {
    public int multiply(int a, int b) {
        return a * b;
    }

    private static void printResult(int result) {
        System.out.println("Result: " + result);
    }

    public static void main(String[] args) {
        Test1 calc = new Test1();
        printResult(calc.multiply(4, 5));
    }
}