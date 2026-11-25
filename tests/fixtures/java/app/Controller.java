package app;

public class Controller {
    private final Service service = new Service();

    public String show() {
        String text = service.get(1);
        String name = service.toString();
        int hash = service.hashCode();
        return text + name + hash;
    }
}
