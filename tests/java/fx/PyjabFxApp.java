/*
 * PyjabFxApp -- a minimal JavaFX application for the pyjab measurement of issue #227.
 *
 * The repository's only test application, tests/java/PyjabTestApp.java, is Swing.  Issue
 * #227 is that the README claims pyjab drives "Swing / AWT / JavaFX ... through Java Access
 * Bridge", while JavaFX on Windows publishes its accessibility through UI Automation
 * (com.sun.glass.ui.win.WinAccessible implements the UIA provider interfaces directly).
 * Nothing has ever pointed pyjab at a JavaFX window, so this application exists to be that
 * window: it is the JavaFX counterpart of PyjabTestApp, deliberately the same shape -- a
 * settable title, a menu bar, and a content area holding a known, countable set of
 * controls.
 *
 * It is in tests/java/fx/ rather than beside PyjabTestApp.java on purpose.
 * tests/conftest.py and eight tools compile tests/java/*.java with the JDK's javac, and
 * JavaFX is not in Temurin -- so a JavaFX source next to PyjabTestApp would make every one
 * of those fail with "package javafx.application does not exist".  A subdirectory keeps it
 * out of that glob and compiles it only from the task that has a JavaFX JDK.
 *
 * It is compiled and launched with a JavaFX-bearing JDK -- Liberica's "jdk+fx" package, or
 * an OpenJFX SDK on --module-path -- and never on a developer machine: a local launch is a
 * Java UI test whether or not it was meant as one (AGENTS.md section 4).
 *
 *     javac -d tests/java/fx/classes tests/java/fx/PyjabFxApp.java
 *     java -cp tests/java/fx/classes PyjabFxApp --title=PyjabFxApp
 *
 * The one thing this application prints is its own widget inventory, and it prints it
 * because the measurement's central number is a count: a reader has to be able to tell "the
 * client saw the window and nothing inside it" from "the window was never there".  The
 * inventory goes to stdout, which the measurement tool redirects to javafx-app.txt; it is
 * the application's own statement of what it built, independent of the tool's copy.
 */

import java.util.Map;

import javafx.application.Application;
import javafx.beans.property.ReadOnlyStringWrapper;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.geometry.Insets;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.Menu;
import javafx.scene.control.MenuBar;
import javafx.scene.control.MenuItem;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.TextField;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;

public class PyjabFxApp extends Application {

    /** The title used when --title= is not given. */
    private static final String DEFAULT_TITLE = "PyjabFxApp";

    /**
     * Every control this application constructs, in creation order.
     *
     * This is the expectation the measurement is read against, and it lives here rather
     * than in the tool so that the application and the tool cannot drift: the tool imports
     * nothing from this file and prints its own copy, the application prints this one, and
     * a difference between javafx-app.txt and the tool's block is itself a finding.
     *
     * Eleven controls.  A complete accessibility tree for the window also carries the
     * containers around them (the BorderPane root, the VBox holding the content, the HBox
     * holding the two buttons, the table's internal header and rows) and the window's own
     * title bar and caption buttons, none of which the application constructs.  So the
     * floor is eleven plus the four table cells below, and the ceiling is not knowable from
     * here -- which is what the measurement is for.
     */
    private static final String[] CONTROL_INVENTORY = {
        "MenuBar",
        "Menu 'File'",
        "MenuItem 'Open'",
        "MenuItem 'Quit'",
        "Label 'FX label'",
        "Button 'FX button one'",
        "Button 'FX button two'",
        "TextField 'fx-text'",
        "TableView",
        "TableColumn 'Name'",
        "TableColumn 'Value'",
    };

    /** The table renders 2 rows x 2 columns, so four cells exist once it is showing. */
    private static final int TABLE_ROWS = 2;
    private static final int TABLE_COLUMNS = 2;

    public static void main(String[] args) {
        launch(args);
    }

    @Override
    public void start(Stage stage) {
        Map<String, String> parameters = getParameters().getNamed();
        String title = parameters.getOrDefault("title", DEFAULT_TITLE);

        stage.setTitle(title);

        BorderPane root = new BorderPane();
        root.setTop(buildMenuBar());

        VBox content = new VBox(8);
        content.setPadding(new Insets(10));

        Label label = new Label("FX label");

        // Two buttons with distinct text, which is what a JavaFX button publishes as its
        // accessible name.
        Button one = new Button("FX button one");
        Button two = new Button("FX button two");
        HBox buttons = new HBox(8, one, two);

        // A text control whose contents a reader can name: for a JavaFX text field the
        // accessible *value* is the text, and there is no separate name unless one is set.
        TextField textField = new TextField("fx-text");

        TableView<ObservableList<String>> table = buildTable();

        content.getChildren().addAll(label, buttons, textField, table);
        root.setCenter(content);

        stage.setScene(new Scene(root, 600, 420));
        stage.show();

        reportInventory(title);
    }

    private static MenuBar buildMenuBar() {
        Menu file = new Menu("File");
        file.getItems().addAll(new MenuItem("Open"), new MenuItem("Quit"));
        MenuBar menuBar = new MenuBar();
        menuBar.getMenus().add(file);
        return menuBar;
    }

    private static TableView<ObservableList<String>> buildTable() {
        TableColumn<ObservableList<String>, String> nameColumn = new TableColumn<>("Name");
        nameColumn.setCellValueFactory(
                (TableColumn.CellDataFeatures<ObservableList<String>, String> data) ->
                        new ReadOnlyStringWrapper(data.getValue().get(0)));

        TableColumn<ObservableList<String>, String> valueColumn = new TableColumn<>("Value");
        valueColumn.setCellValueFactory(
                (TableColumn.CellDataFeatures<ObservableList<String>, String> data) ->
                        new ReadOnlyStringWrapper(data.getValue().get(1)));

        TableView<ObservableList<String>> table = new TableView<>();
        table.getColumns().add(nameColumn);
        table.getColumns().add(valueColumn);
        table.getItems().addAll(
                FXCollections.observableArrayList("alpha", "one"),
                FXCollections.observableArrayList("beta", "two"));
        table.setPrefHeight(140);
        return table;
    }

    /**
     * Print what this application built, and the versions it is running on, then flush.
     *
     * The tool reads this file instead of the process' stdout pipe, so nothing here can
     * block the application if the tool stops reading.
     */
    private static void reportInventory(String title) {
        System.out.println("--- PyjabFxApp inventory (what the application itself says it built) ---");
        System.out.println("title=" + title);
        System.out.println("java.version=" + System.getProperty("java.version"));
        System.out.println("java.home=" + System.getProperty("java.home"));
        System.out.println("javafx.version=" + System.getProperty("javafx.version", "(unset)"));
        System.out.println("javafx.runtime.version="
                + System.getProperty("javafx.runtime.version", "(unset)"));
        for (String control : CONTROL_INVENTORY) {
            System.out.println("control=" + control);
        }
        System.out.println("control_count=" + CONTROL_INVENTORY.length);
        System.out.println("table_rows=" + TABLE_ROWS);
        System.out.println("table_columns=" + TABLE_COLUMNS);
        System.out.println("cell_count=" + (TABLE_ROWS * TABLE_COLUMNS));
        System.out.println("expected_content_elements_at_least="
                + (CONTROL_INVENTORY.length + TABLE_ROWS * TABLE_COLUMNS));
        System.out.println("--- end inventory ---");
        System.out.flush();
    }
}
