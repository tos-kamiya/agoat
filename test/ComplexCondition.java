public class ComplexCondition {
	public static void main(String[] args) {
		if (args.length == 1 && (args[0].equals("-h") || args[0].equals("--help"))) {
			System.out.println("usage: ComplexCondition [-h|--help]");
			System.exit(1);
		}
		if (args.length > 0) {
			System.err.println("too many command-line arguments!");
			System.exit(1);
		}
		System.out.println("Done!");
	}
}

