// Extract the SvelteKit hydration `data: [...]` literal from a page and write it as JSON.
const fs = require('fs'), vm = require('vm');
const [,, inFile, outFile] = process.argv;
const s = fs.readFileSync(inFile, 'utf8');
const start = s.indexOf('data: [', s.indexOf('kit.start'));
let i = s.indexOf('[', start), depth = 0, inStr = null;
for (let j = i; j < s.length; j++) {
  const c = s[j];
  if (inStr) { if (c === '\\') j++; else if (c === inStr) inStr = null; continue; }
  if (c === '"' || c === "'" || c === '`') inStr = c;
  else if (c === '[' || c === '{') depth++;
  else if (c === ']' || c === '}') { if (--depth === 0) { var end = j + 1; break; } }
}
const data = vm.runInNewContext('(' + s.slice(i, end) + ')', Object.create(null), { timeout: 2000 });
fs.writeFileSync(outFile, JSON.stringify(data));
console.log('wrote', outFile, fs.statSync(outFile).size);
