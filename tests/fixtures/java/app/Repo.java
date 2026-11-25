package app;

public class Repo {
    public String find(int id) {
        return "item" + id;
    }

    public String lookup(String key) {
        return key + "!";
    }

    public static Repo create() {
        return new Repo();
    }
}
