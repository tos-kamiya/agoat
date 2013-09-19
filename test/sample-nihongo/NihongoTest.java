import static org.hamcrest.core.Is.is;
import static org.junit.Assert.assertThat;
import org.junit.Test;

public class NihongoTest {
    @Test
    public void 挨拶の言葉() {
        Nihongo n = new Nihongo();
        assertThat(n.挨拶(), is("こんにちは！"));
    }
}
