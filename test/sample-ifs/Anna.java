import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Anna {
	private static final Pattern r_hp = Pattern.compile("HP");
	private static final Pattern r_dx = Pattern.compile("DX");
	private static final Pattern r_mp = Pattern.compile("MP");

	public boolean parse() {
		String s = "123abc";

		Matcher m_hp = r_hp.matcher(s);
		if(! m_hp.find())
			return false;

		Matcher m_dx = r_dx.matcher(s);
		if(! m_dx.find())
			return false;

		Matcher m_mp = r_mp.matcher(s);
		if(! m_mp.find())
			return false;

		return true;
	}

	public static void main(String[] args) {
		if (new Anna().parse()) {
			System.out.println("true");
		}
	}
}


