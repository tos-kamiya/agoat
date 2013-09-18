interface HavingSignaturePhrase {
    String getPhrase();
}

class Player implements HavingSignaturePhrase {
    String name = "SteelGuy";
    public String getName() {
        return name;
    }
    public String getPhrase() {
        return getName() + " is here.";
    }
}

class Monster implements HavingSignaturePhrase {
    String mood = "angry";
    public String getMood() {
        return mood;
    }
    public String getPhrase() {
        return "I'm " + getMood() + "!";
    }
}

class SignaturePhrase {
    public static void say(HavingSignaturePhrase one) {
        System.out.println(one.getPhrase());
    }
    public static void main(String[] args) {
        HavingSignaturePhrase p = new Player();
        HavingSignaturePhrase m = new Monster();
        say(p);
        say(m);
    }
}

