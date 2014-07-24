public class Recursive {
	public int calc(int n) {
		if (n <= 1) {
			return n;
		}
		if (n % 2 == 0) {
			return calc(n / 2);
		} else {
			return calc2(n);
		}
	}
	public int calc2(int n) {
		return calc(n * 3 + 1);
	}
}

