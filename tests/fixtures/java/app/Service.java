package app;

import java.util.List;

public class Service extends Base {
    private final Repo repo = Repo.create();

    public String get(int id) {
        log("get");
        return repo.find(id);
    }

    public List<String> all(List<String> keys) {
        return keys.stream().map(repo::lookup).toList();
    }

    public Runnable task() {
        return new Runnable() {
            @Override
            public void run() {
                repo.find(1);
            }
        };
    }

    @Override
    public String toString() {
        return "Service";
    }
}
