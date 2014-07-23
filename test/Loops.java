import java.util.*;

public class Loops {
	public static void whileLoop() {
		int i = 1; 
		while (i < 10) {
			System.out.println(i);
			i = i * 2;
		}
	}
	public static void forIntLoop() {
		for (int i = 0; i < 10; ++i) {
			System.out.println(i);
		}
	}
	public static void forArrayIterator() {
		int[] a = new int [] { 0, 1, 2, 3, 4, 5 };
		for (int item : a) {
			System.out.println(item);
		}
	}
	public static void forListIterator() {
		ArrayList<Integer> a = new ArrayList<Integer>();
		for (int item : a) {
			System.out.println(item);
		}
	}
}

