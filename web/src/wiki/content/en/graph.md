# Call graph

The three methods receive the same static call graph between classes, extracted from the compiled code of each application. The extraction code is in `src/monosplit/extraction/`.

## Extraction

1. The application is cloned and pinned to a commit. The extraction refuses a checkout with local changes.
2. The code is built with Maven, through the project's wrapper or the Maven 3.9.16 that the tool installs, or with the project's Gradle wrapper, for AcmeAir. For JPetStore, the plugins of the parent POM (Project Object Model) that rewrite sources are skipped, and the tool fails if the build changes a tracked file.
3. `javap -v -p` from Eclipse Temurin 21, a JDK (Java Development Kit) installed by the tool, reads the bytecode of each class. The compiler has already resolved the static type of every call, which a source-code parser would have to approximate.

## Counting rules

- **Nodes:** top-level classes of `src/main/java`, including interfaces, enums and abstract classes; tests are excluded. Nested, inner and anonymous classes are merged into the top-level class that contains them.
- **Call:** one invocation instruction (`invokevirtual`, `invokespecial`, `invokestatic`, `invokeinterface`) or one method reference in an `invokedynamic`, such as `Item::getListPrice`, whose target is another class of the application. Constructor calls count.
- **Target:** the class that declares the invoked member. An inherited method is attributed to the application superclass or interface that declares it; members declared only in library types are library calls.
- **Not counted:** calls inside a class, calls to libraries, field accesses, type references without a call, and calls made by a framework at run time, such as those of Stripes, of MyBatis XML (Extensible Markup Language) mappers and of expressions in JSP (JavaServer Pages) pages.
- **Edge:** an ordered pair of classes with at least one call; the weight of the edge is the number of calls.
- **Isolated classes** stay in the graph and must be assigned by every method. In JPetStore, `Category` is isolated: no Java code calls its methods; only the JSP pages use it.

JPetStore 6.3.0 has 24 classes, 40 edges, 159 calls and 1 isolated class. Version 6.4.0 replaced the web layer with Spring MVC and has 25 classes; 6.3.0 is the last version with the 24 classes decomposed in the literature.

AcmeAir, in its MongoDB deployment, has 52 classes, 72 edges, 220 calls and 6 isolated classes: two interfaces of constants, whose values the compiler copies into the classes that use them, and four classes that the framework or the server finds through annotations.

## Manual check

A sample of 20 edges, drawn with a seed when the graph is extracted, is checked in the source code on the [Data](#/data?tab=edges) page. For each edge, the page lists up to three places of the call (file and line); whoever checks marks yes, when the lines contain the calls, or no, and may leave a note. The result is stored in the database with the graph, and every change goes to the change log.

## What the graph represents

The graph is static: it counts the places in the code where one class invokes another, not how many times this happens at run time. Dependencies created by a framework at run time are left out. These choices apply equally to the three methods, because all of them receive the same graph and are measured with the same scripts.
