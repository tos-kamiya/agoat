public class NestedLoopAndBranches {
	public static void main(String[] args) {
		for (int i = 0; i < 10; ++i) {
			int j = i;
			while (j < 10) {
				if (i * j % 3 == 1) {
					System.out.format("%d * %d == 1 mod 3\n", i, j);
					j += 1;
				} else {
					j += 2;
				}
			}
		}
	}
}

