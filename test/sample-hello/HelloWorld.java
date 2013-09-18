class HelloWorld {
    public static void helloWorld() {
        System.out.print("Hello, ");
        System.out.println("World!");
    }
    public void helloSomeone(String who) {
        System.out.format("Hello, %s!\n", who);
    }
    public static void main(String[] args) {
        if (args.length == 0) {
            helloWorld();
        } else {
            new HelloWorld().helloSomeone(args[0]);
        }
    }
}

