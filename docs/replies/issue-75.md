Thanks for reporting this -- and sorry for the silence.

You are not doing anything wrong: pyjab has never documented how to find
locators, and that is a real gap. I have just rewritten the README with a
dedicated "Finding locators" section. Short version:

**1. Install [Access Bridge Explorer](https://github.com/google/access-bridge-explorer).**
Expand the tree of your target application. Every node shows exactly the
fields pyjab exposes: `name`, `description`, `role`, `states`,
`indexInParent`, `bounds`. Whatever you see there is what you pass to
`find_element_by_*`.

**2. Pick the locator that matches what you can see:**

```python
driver.find_element_by_name("Submit")                    # accessible name
driver.find_element_by_role("push button")               # no useful name
driver.find_element_by_index_in_parent(3)                # neither name nor role
driver.find_element_by_xpath("//push button[@name=contains('OK')]")
```

**3. If a control has no accessible name**, call
`driver.find_elements_by_role("...")` first and print what comes back -- a
sibling or parent usually carries the label you want.

The most common mistake is using the *visible* label as the name. They are
often different (a button labelled "Login" frequently has the accessible name
`"Login"` but sometimes `"Login..."`, `"&Login"` or nothing at all).
Access Bridge Explorer removes the guesswork.

If you are still stuck, paste the output of
`driver.find_elements_by_role("<role>")` for the window you are working with
and I will help you write the locator.
