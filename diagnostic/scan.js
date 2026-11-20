const fs = require("fs");
const acorn = require("acorn");
const code = fs.readFileSync("diagnostic/inline-007.js", "utf8");
const tokenizer = acorn.tokenizer(code, { ecmaVersion: "latest", locations: true });
const stack = [];
const opens = { "(": ")", "[": "]", "{": "}" };
const errors = [];
try {
  for (;;) {
    const token = tokenizer.getToken();
    const label = token.type.label;
    if (label === "${") {
      stack.push({ open: "${", close: "}", line: token.loc.start.line, column: token.loc.start.column });
    } else if (opens[label]) {
      stack.push({ open: label, close: opens[label], line: token.loc.start.line, column: token.loc.start.column });
    } else if ([")", "]", "}"].includes(label)) {
      const top = stack[stack.length - 1];
      if (top && top.close === label) stack.pop();
      else errors.push({ label, line: token.loc.start.line, column: token.loc.start.column, top });
    }
    if (label === "eof") break;
  }
  console.log("UNMATCHED_CLOSERS=" + JSON.stringify(errors.slice(0, 50)));
  console.log("UNCLOSED_OPENERS=" + JSON.stringify(stack.slice(-80)));
} catch (error) {
  console.log("TOKENIZER_ERROR=" + error.message);
  console.log("TOKENIZER_LOCATION=" + JSON.stringify(error.loc || null));
  console.log("STACK_AT_ERROR=" + JSON.stringify(stack.slice(-80)));
}
