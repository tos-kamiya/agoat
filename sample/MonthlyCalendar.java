import java.util.*;

public class MonthlyCalendar {
	public static void main(String[] args) {
		int year = Integer.valueOf(args[0]);
		int month = Integer.valueOf(args[1]);
		printCalendarMonthYear(month, year);
	}

	private static void printFields(String[] fields) {
		for (String field : fields)
			System.out.format("%4s", field == null ? "":field);
		System.out.println("");
	}

	private static void printCalendarMonthYear(int month, int year) {
		Calendar cal = new GregorianCalendar();
		cal.clear();
		cal.set(year, month - 1, 1);

		int weekdayOf1st = cal.get(Calendar.DAY_OF_WEEK);
		int daysInMonth = cal.getActualMaximum(Calendar.DAY_OF_MONTH);

		String[] buf = "Sun Mon Tue Wed Thu Fri Sat".split(" ");
		printFields(buf);

		int column = weekdayOf1st - 1;
		buf = new String[7];
		for (int day = 1; day <= daysInMonth; ++day) {
			buf[column] = String.valueOf(day);
			column = (column + 1) % 7;
			if (column == 0) {
				printFields(buf);
				buf = new String[7];
			}
		}
		if (column != 0)
			printFields(buf);
	}
}
