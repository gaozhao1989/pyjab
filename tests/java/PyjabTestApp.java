/*
 * PyjabTestApp -- a single-file Swing application for the pyjab GUI test suite.
 *
 * The GUI tests used to download 27 demo applets from docs.oracle.com and drive
 * those.  Every run therefore needed a third party to stay online, a working
 * Java Web Start, and the exact widget names inside somebody else's demos.
 * This application replaces them: it lives in this repository, is compiled on
 * demand by the test fixtures, and defines every widget the tests look for.
 * The suite has no network dependency as a result.
 *
 * It is plain JDK Swing: no third-party libraries, no resource files, no image
 * files, no modal dialog at startup, and nothing hidden behind a tab, so every
 * component is showing and findable as soon as the frame appears.
 *
 *     javac -d classes tests/java/PyjabTestApp.java
 *     java -cp classes PyjabTestApp
 *
 * The cross-platform (Metal) look and feel is installed deliberately, before
 * any component is created.  With the system look and feel the accessibility
 * names, roles and even the component hierarchy differ between machines and
 * locales, and the tests would end up asserting things about the host rather
 * than about pyjab.
 */

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;

import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.ButtonGroup;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JCheckBoxMenuItem;
import javax.swing.JColorChooser;
import javax.swing.JComboBox;
import javax.swing.JComponent;
import javax.swing.JDesktopPane;
import javax.swing.JDialog;
import javax.swing.JFrame;
import javax.swing.JInternalFrame;
import javax.swing.JLabel;
import javax.swing.JList;
import javax.swing.JMenu;
import javax.swing.JMenuBar;
import javax.swing.JMenuItem;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JPasswordField;
import javax.swing.JPopupMenu;
import javax.swing.JProgressBar;
import javax.swing.JRadioButton;
import javax.swing.JScrollPane;
import javax.swing.JSeparator;
import javax.swing.JSlider;
import javax.swing.JSpinner;
import javax.swing.JSplitPane;
import javax.swing.JTable;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.JToolBar;
import javax.swing.JTree;
import javax.swing.SpinnerListModel;
import javax.swing.SwingConstants;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;
import javax.swing.table.DefaultTableModel;
import javax.swing.tree.DefaultMutableTreeNode;
import javax.swing.tree.DefaultTreeModel;

public class PyjabTestApp {

    /** The window title the test suite binds to; also used as the frame name. */
    private static final String FRAME_TITLE = "PyjabTestApp";

    /** Widths of the three columns of the main panel. */
    private static final int BUTTON_COLUMN_WIDTH = 240;
    private static final int INPUT_COLUMN_WIDTH = 310;
    private static final int TABLE_COLUMN_WIDTH = 390;

    public static void main(String[] args) {
        // Install the cross-platform look and feel before creating any
        // component, so that names, roles and the component hierarchy are
        // identical on every machine and in every locale.
        try {
            UIManager.setLookAndFeel(UIManager.getCrossPlatformLookAndFeelClassName());
        } catch (Exception ex) {
            System.err.println("Could not install the cross-platform look and feel: " + ex);
        }

        // Build and show the whole UI on the Event Dispatch Thread, and return
        // from main immediately: nothing here may block.
        SwingUtilities.invokeLater(new Runnable() {
            public void run() {
                buildAndShowUi();
            }
        });
    }

    /**
     * Creates the single frame: menu bar, tool bar and one main panel holding
     * every component the tests look for.
     */
    private static void buildAndShowUi() {
        JFrame frame = new JFrame(FRAME_TITLE);
        frame.setName(FRAME_TITLE);
        // The automation framework terminates the process; the application
        // should still close cleanly when the user does it instead.
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);

        frame.setJMenuBar(buildMenuBar());

        JPanel contentPane = new JPanel(new BorderLayout());
        contentPane.setName("Content pane");
        contentPane.add(buildToolBar(), BorderLayout.NORTH);
        contentPane.add(buildMainPanel(frame), BorderLayout.CENTER);
        frame.setContentPane(contentPane);

        frame.setSize(1000, 800);
        frame.setLocationRelativeTo(null);
        frame.setVisible(true);
    }

    // ------------------------------------------------------------------
    // Menu bar
    // ------------------------------------------------------------------
    // Supports the "menu bar", "menu", "menu item", "check box menu item"
    // and "separator" lookups, plus selecting an item from "A Menu".
    private static JMenuBar buildMenuBar() {
        JMenuBar menuBar = new JMenuBar();
        menuBar.setName("Menu bar");

        JMenu aMenu = new JMenu("A Menu");
        aMenu.setName("A Menu");

        JMenuItem anotherOne = new JMenuItem("Another one");
        anotherOne.setName("Another one");
        aMenu.add(anotherOne);

        JCheckBoxMenuItem checkBoxMenuItem = new JCheckBoxMenuItem("A check box menu item");
        checkBoxMenuItem.setName("A check box menu item");
        aMenu.add(checkBoxMenuItem);

        aMenu.add(new JSeparator());

        JMenuItem lastOne = new JMenuItem("Last one");
        lastOne.setName("Last one");
        aMenu.add(lastOne);

        JMenu anotherMenu = new JMenu("Another Menu");
        anotherMenu.setName("Another Menu");
        JMenuItem thirdItem = new JMenuItem("Third item");
        thirdItem.setName("Third item");
        anotherMenu.add(thirdItem);

        menuBar.add(aMenu);
        menuBar.add(anotherMenu);
        return menuBar;
    }

    // ------------------------------------------------------------------
    // Tool bar
    // ------------------------------------------------------------------
    // Supports the "tool bar" and "push button" lookups for the button that
    // lives on the tool bar.
    private static JToolBar buildToolBar() {
        JToolBar toolBar = new JToolBar();
        // Docked, not floating: a floating tool bar is its own top-level
        // window, and its button would then not be part of the frame.
        toolBar.setFloatable(false);

        JButton toolBarButton = new JButton("Toolbar Button");
        toolBarButton.setName("Toolbar Button");
        toolBar.add(toolBarButton);
        return toolBar;
    }

    // ------------------------------------------------------------------
    // Main panel: three columns side by side
    // ------------------------------------------------------------------
    private static JPanel buildMainPanel(final JFrame frame) {
        JPanel mainPanel = new JPanel(new GridBagLayout());
        mainPanel.setName("Main panel");

        JPanel buttonColumn = buildButtonColumn(frame);
        buttonColumn.setPreferredSize(new Dimension(BUTTON_COLUMN_WIDTH, 620));
        JPanel inputColumn = buildInputColumn();
        inputColumn.setPreferredSize(new Dimension(INPUT_COLUMN_WIDTH, 620));
        JPanel tableColumn = buildTableColumn();
        tableColumn.setPreferredSize(new Dimension(TABLE_COLUMN_WIDTH, 620));

        mainPanel.add(buttonColumn, columnConstraints(0, 0.0, 10));
        mainPanel.add(inputColumn, columnConstraints(1, 0.0, 6));
        mainPanel.add(tableColumn, columnConstraints(2, 1.0, 6));
        return mainPanel;
    }

    private static GridBagConstraints columnConstraints(int column, double weightX, int leftInset) {
        GridBagConstraints constraints = new GridBagConstraints();
        constraints.gridx = column;
        constraints.gridy = 0;
        constraints.gridheight = 1;
        constraints.weightx = weightX;
        constraints.weighty = 1.0;
        constraints.fill = GridBagConstraints.BOTH;
        constraints.anchor = GridBagConstraints.NORTHWEST;
        constraints.insets = new Insets(10, leftInset, 10, 0);
        return constraints;
    }

    /**
     * Adds one row to a vertical column.  The row is capped at its preferred
     * height so that the vertical glue at the bottom of the column absorbs the
     * frame's spare height instead of the rows being stretched.
     */
    private static void addRow(JPanel column, JComponent row) {
        row.setAlignmentX(Component.LEFT_ALIGNMENT);
        Dimension preferred = row.getPreferredSize();
        row.setMaximumSize(new Dimension(Integer.MAX_VALUE, (int) preferred.getHeight()));
        column.add(row);
        column.add(Box.createVerticalStrut(6));
    }

    /** A one-line row: a label on the left, the component filling the rest. */
    private static JPanel buildLabeledRow(String labelText, JComponent component, int height) {
        JPanel row = new JPanel(new BorderLayout(6, 0));
        JLabel label = new JLabel(labelText);
        label.setName(labelText);
        row.add(label, BorderLayout.WEST);
        row.add(component, BorderLayout.CENTER);
        row.setName(labelText + " row");
        row.setPreferredSize(new Dimension(INPUT_COLUMN_WIDTH - 10, height));
        return row;
    }

    // ------------------------------------------------------------------
    // Column one: buttons, check boxes, radio buttons, a label
    // ------------------------------------------------------------------
    // Supports the "push button" enable/disable behaviour, and opening the
    // dialog, alert, colour chooser and popup windows -- each of which is a
    // genuinely new, non-modal top-level window created on every click.
    private static JPanel buildButtonColumn(final JFrame frame) {
        JPanel column = new JPanel();
        column.setName("Button column");
        column.setLayout(new BoxLayout(column, BoxLayout.Y_AXIS));

        final JButton middleButton = new JButton("Middle button");
        middleButton.setName("Middle button");

        JButton disableButton = new JButton("Disable middle button");
        disableButton.setName("Disable middle button");
        disableButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent event) {
                middleButton.setEnabled(false);
            }
        });

        JButton enableButton = new JButton("Enable middle button");
        enableButton.setName("Enable middle button");
        enableButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent event) {
                middleButton.setEnabled(true);
            }
        });

        // A new modeless dialog each time: modeless so that it does not block
        // the Event Dispatch Thread, and new so that the message pump test can
        // watch a second top-level window appear after a plain (non-simulated)
        // click.
        JButton showDialogButton = new JButton("Show dialog");
        showDialogButton.setName("Show dialog");
        showDialogButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent event) {
                JDialog dialog = new JDialog(frame, "A Dialog", false);
                dialog.setName("A Dialog");

                JLabel dialogLabel = new JLabel("Dialog label");
                dialogLabel.setName("Dialog label");

                final JDialog target = dialog;
                JButton closeDialogButton = new JButton("Close dialog");
                closeDialogButton.setName("Close dialog");
                closeDialogButton.addActionListener(new ActionListener() {
                    public void actionPerformed(ActionEvent closeEvent) {
                        target.dispose();
                    }
                });

                JPanel panel = new JPanel(new BorderLayout(6, 6));
                panel.add(dialogLabel, BorderLayout.CENTER);
                panel.add(closeDialogButton, BorderLayout.SOUTH);
                dialog.setContentPane(panel);
                dialog.setSize(300, 150);
                dialog.setLocationRelativeTo(frame);
                dialog.setVisible(true);
            }
        });

        // A JOptionPane would be modal in some look and feels, and the tests
        // only need a second window carrying a label, so this is a plain
        // modeless dialog as well.
        JButton showAlertButton = new JButton("Show alert");
        showAlertButton.setName("Show alert");
        showAlertButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent event) {
                JDialog dialog = new JDialog(frame, "An Alert", false);
                dialog.setName("An Alert");

                // A JOptionPane, not a bare panel: it is the component whose
                // accessibility role is "alert", which is what the suite checks.
                JOptionPane alertPane = new JOptionPane(
                        "Alert message", JOptionPane.WARNING_MESSAGE);
                alertPane.setName("Alert message");
                dialog.setContentPane(alertPane);
                dialog.setSize(320, 160);
                dialog.setLocationRelativeTo(frame);
                dialog.setVisible(true);
            }
        });

        JButton showColorChooserButton = new JButton("Show color chooser");
        showColorChooserButton.setName("Show color chooser");
        showColorChooserButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent event) {
                JDialog dialog = new JDialog(frame, "A Color Chooser", false);
                dialog.setName("A Color Chooser");

                // The chooser supplies the "color chooser" accessibility role
                // and its HSV/HSL/RGB/Swatches page tabs.  It sits inside a
                // plain content panel so that it is a child of the dialog
                // rather than being the dialog's content pane itself.
                JColorChooser colorChooser = new JColorChooser();
                JPanel panel = new JPanel(new BorderLayout());
                panel.add(colorChooser, BorderLayout.CENTER);
                dialog.setContentPane(panel);
                dialog.setSize(600, 400);
                dialog.setLocationRelativeTo(frame);
                dialog.setVisible(true);
            }
        });

        final JButton showPopupButton = new JButton("Show popup");
        showPopupButton.setName("Show popup");
        showPopupButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent event) {
                JPopupMenu popupMenu = new JPopupMenu();
                popupMenu.setName("Popup menu");

                JMenuItem popupOne = new JMenuItem("Popup one");
                popupOne.setName("Popup one");
                popupMenu.add(popupOne);

                JMenuItem popupTwo = new JMenuItem("Popup two");
                popupTwo.setName("Popup two");
                popupMenu.add(popupTwo);

                popupMenu.add(new JSeparator());
                popupMenu.show(showPopupButton, 0, showPopupButton.getHeight());
            }
        });

        addRow(column, disableButton);
        addRow(column, middleButton);
        addRow(column, enableButton);
        addRow(column, showDialogButton);
        addRow(column, showAlertButton);
        addRow(column, showColorChooserButton);
        addRow(column, showPopupButton);

        // Supports the "label" lookup.
        JLabel aLabel = new JLabel("A Label");
        aLabel.setName("A Label");
        addRow(column, aLabel);

        // Supports the "check box" lookups by name: the text is the
        // accessibility name, and setName pins it down as well.
        JCheckBox chinCheckBox = new JCheckBox("Chin");
        chinCheckBox.setName("Chin");
        JCheckBox hairCheckBox = new JCheckBox("Hair");
        hairCheckBox.setName("Hair");
        JPanel checkBoxRow = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        checkBoxRow.setName("Check boxes");
        checkBoxRow.add(chinCheckBox);
        checkBoxRow.add(hairCheckBox);
        addRow(column, checkBoxRow);

        // Supports the "radio button" lookups and the checked state: Cat
        // starts selected, and only one of the two can be selected.
        JRadioButton catRadioButton = new JRadioButton("Cat");
        catRadioButton.setName("Cat");
        catRadioButton.setSelected(true);
        JRadioButton dogRadioButton = new JRadioButton("Dog");
        dogRadioButton.setName("Dog");
        ButtonGroup animalGroup = new ButtonGroup();
        animalGroup.add(catRadioButton);
        animalGroup.add(dogRadioButton);
        JPanel radioButtonRow = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        radioButtonRow.setName("Radio buttons");
        radioButtonRow.add(catRadioButton);
        radioButtonRow.add(dogRadioButton);
        addRow(column, radioButtonRow);

        column.add(Box.createVerticalGlue());
        return column;
    }

    // ------------------------------------------------------------------
    // Column two: list, combo box, text components, tree, sliders,
    // spinner, progress bar
    // ------------------------------------------------------------------
    private static JPanel buildInputColumn() {
        JPanel column = new JPanel();
        column.setName("Input column");
        column.setLayout(new BoxLayout(column, BoxLayout.Y_AXIS));

        // Supports the "list" lookup and selecting an item by name.  The
        // model holds exactly these four strings, in this order.
        JList<String> list = new JList<String>(
                new String[] {"John Smith", "Kathy Green", "May", "Steve"});
        list.setName("Names list");
        JScrollPane listScrollPane = new JScrollPane(list);
        listScrollPane.setName("Names list scroll pane");
        listScrollPane.setPreferredSize(new Dimension(INPUT_COLUMN_WIDTH - 10, 100));
        addRow(column, listScrollPane);

        // Supports the "combo box" lookup and selecting an option by name.
        // Bird is selected initially.
        JComboBox<String> comboBox = new JComboBox<String>(
                new String[] {"Bird", "Cat", "Dog", "Rabbit", "Pig"});
        comboBox.setName("Animals combo box");
        comboBox.setSelectedItem("Bird");
        JPanel comboBoxRow = new JPanel(new BorderLayout(6, 0));
        comboBoxRow.setName("Combo box row");
        JLabel comboBoxLabel = new JLabel("Combo box");
        comboBoxLabel.setName("Combo box");
        comboBoxRow.add(comboBoxLabel, BorderLayout.WEST);
        comboBoxRow.add(comboBox, BorderLayout.CENTER);
        comboBoxRow.setPreferredSize(new Dimension(INPUT_COLUMN_WIDTH - 10, 28));
        addRow(column, comboBoxRow);

        // Supports the "text" role lookup.  The initial text is the phone
        // number, so the accessibility name matches it; the field stays
        // editable so text can be typed into and cleared.
        JTextField textField = new JTextField("1122233455");
        textField.setName("1122233455");
        addRow(column, textField);

        // Supports the "password text" role lookup.
        JPasswordField passwordField = new JPasswordField("secret");
        passwordField.setName("password");
        addRow(column, passwordField);

        // Supports the "text" role lookup for a multi-line component, inside a
        // scroll pane as a text area must be.
        JTextArea textArea = new JTextArea("Text area contents");
        textArea.setName("Text area contents");
        textArea.setRows(3);
        textArea.setLineWrap(false);
        JScrollPane textAreaScrollPane = new JScrollPane(textArea);
        textAreaScrollPane.setName("Text area scroll pane");
        textAreaScrollPane.setPreferredSize(new Dimension(INPUT_COLUMN_WIDTH - 10, 90));
        addRow(column, textAreaScrollPane);

        // Supports the "tree" and "viewport" lookups, plus expanding a node by
        // name.  Root with two children, each with two leaves; every row is
        // expanded here so the whole tree is showing from the start.
        DefaultMutableTreeNode root = new DefaultMutableTreeNode("Root");
        DefaultMutableTreeNode childOne = new DefaultMutableTreeNode("Child one");
        childOne.add(new DefaultMutableTreeNode("Child one leaf A"));
        childOne.add(new DefaultMutableTreeNode("Child one leaf B"));
        DefaultMutableTreeNode childTwo = new DefaultMutableTreeNode("Child two");
        childTwo.add(new DefaultMutableTreeNode("Child two leaf A"));
        childTwo.add(new DefaultMutableTreeNode("Child two leaf B"));
        root.add(childOne);
        root.add(childTwo);
        JTree tree = new JTree(new DefaultTreeModel(root));
        tree.setName("Tree");
        for (int row = 0; row < tree.getRowCount(); row++) {
            tree.expandRow(row);
        }
        JScrollPane treeScrollPane = new JScrollPane(tree);
        treeScrollPane.setName("Tree scroll pane");
        // Tall enough for all seven expanded rows, so no tree row is clipped
        // and the tree needs no scroll bar of its own.
        treeScrollPane.setPreferredSize(new Dimension(INPUT_COLUMN_WIDTH - 10, 165));
        addRow(column, treeScrollPane);

        // Supports the "slider" role lookup and sliding to either end.  The
        // second one is found by name, so it carries one.
        JSlider firstSlider = new JSlider(SwingConstants.HORIZONTAL, 0, 100, 0);
        firstSlider.setName("First slider");
        addRow(column, buildLabeledRow("First slider", firstSlider, 45));

        JSlider secondSlider = new JSlider(SwingConstants.HORIZONTAL, 0, 100, 100);
        secondSlider.setName("Second slider");
        addRow(column, buildLabeledRow("Second slider", secondSlider, 45));

        // Supports the "spinbox" role lookup and spinning by name or by value.
        String[] years = new String[10];
        for (int i = 0; i < years.length; i++) {
            years[i] = Integer.toString(2001 + i);
        }
        JSpinner spinner = new JSpinner(new SpinnerListModel(years));
        spinner.setName("Year");
        addRow(column, buildLabeledRow("Year", spinner, 28));

        // Supports the "progress bar" role lookup; the string is painted so
        // the value is readable through the accessibility text as well.
        JProgressBar progressBar = new JProgressBar(SwingConstants.HORIZONTAL, 0, 100);
        progressBar.setName("Progress bar");
        progressBar.setValue(40);
        progressBar.setStringPainted(true);
        progressBar.setBorderPainted(true);
        addRow(column, buildLabeledRow("Progress", progressBar, 40));

        column.add(Box.createVerticalGlue());
        return column;
    }

    // ------------------------------------------------------------------
    // Column three: table, scroll bars, split pane, desktop pane
    // ------------------------------------------------------------------
    private static JPanel buildTableColumn() {
        JPanel column = new JPanel();
        column.setName("Table column");
        column.setLayout(new BoxLayout(column, BoxLayout.Y_AXIS));

        // Supports the "table" role lookup and reading a cell by row/column.
        Object[] columnNames = {"Name", "Sport", "# of Years", "Vegetarian"};
        Object[][] rowData = {
            {"Kathy", "Snowboarding", Integer.valueOf(5), Boolean.FALSE},
            {"John", "Rowing", Integer.valueOf(3), Boolean.TRUE},
            {"Sue", "Knitting", Integer.valueOf(2), Boolean.TRUE},
            {"Jane", "Speed reading", Integer.valueOf(5), Boolean.FALSE},
            {"Joe", "Pool", Integer.valueOf(10), Boolean.TRUE},
        };
        JTable table = new JTable(new DefaultTableModel(rowData, columnNames));
        table.setName("Sports table");
        table.setFillsViewportHeight(true);
        JScrollPane tableScrollPane = new JScrollPane(table);
        tableScrollPane.setName("Sports table scroll pane");
        // Tall enough for the header and all five rows, so the whole table is
        // showing rather than clipped by the viewport.
        tableScrollPane.setPreferredSize(new Dimension(TABLE_COLUMN_WIDTH - 10, 150));
        addRow(column, tableScrollPane);

        // Supports the "scroll bar" lookups for the vertical and the
        // horizontal states.  The content is both taller and wider than the
        // viewport, so both bars are needed and both are showing.
        JPanel bigContent = new JPanel();
        bigContent.setName("Scroll bar content");
        bigContent.setBackground(Color.WHITE);
        bigContent.setPreferredSize(new Dimension(900, 400));
        JScrollPane scrollBarScrollPane = new JScrollPane(bigContent);
        scrollBarScrollPane.setName("Scroll bar scroll pane");
        scrollBarScrollPane.setPreferredSize(new Dimension(TABLE_COLUMN_WIDTH - 10, 130));
        addRow(column, scrollBarScrollPane);

        // Supports the "split pane" role lookup.  The divider is placed so
        // that both sides of the split are visible straight away.
        JPanel leftPanel = new JPanel(new BorderLayout());
        leftPanel.setName("Left split panel");
        JLabel leftLabel = new JLabel("Left");
        leftLabel.setName("Left");
        leftPanel.add(leftLabel, BorderLayout.CENTER);
        JPanel rightPanel = new JPanel(new BorderLayout());
        rightPanel.setName("Right split panel");
        JLabel rightLabel = new JLabel("Right");
        rightLabel.setName("Right");
        rightPanel.add(rightLabel, BorderLayout.CENTER);
        JSplitPane splitPane = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, leftPanel, rightPanel);
        splitPane.setName("Split pane");
        splitPane.setDividerLocation(150);
        splitPane.setPreferredSize(new Dimension(TABLE_COLUMN_WIDTH - 10, 80));
        addRow(column, splitPane);

        // Supports the "internal frame" role lookup.  The desktop pane is
        // visible and the internal frame is visible (not iconified), so it
        // reports as showing without any interaction.
        JDesktopPane desktopPane = new JDesktopPane();
        desktopPane.setName("Desktop pane");
        desktopPane.setPreferredSize(new Dimension(TABLE_COLUMN_WIDTH - 10, 150));
        JInternalFrame internalFrame =
                new JInternalFrame("An Internal Frame", true, true, true, true);
        internalFrame.setName("An Internal Frame");
        internalFrame.setSize(220, 100);
        internalFrame.setLocation(20, 20);
        desktopPane.add(internalFrame);
        internalFrame.setVisible(true);
        addRow(column, desktopPane);

        column.add(Box.createVerticalGlue());
        return column;
    }
}
