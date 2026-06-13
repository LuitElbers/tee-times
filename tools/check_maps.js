// Validates public/index.html enrichment maps after adding courses.
// Checks the 4 maps (COURSE_ORDER / COURSE_COLORS / COURSE_COORDS / COURSE_TAGS)
// have IDENTICAL key sets — catches a course added to one map but missing from
// another (the #1 enrichment bug). Run: `node tools/check_maps.js`
const fs = require('fs');
const html = fs.readFileSync('public/index.html', 'utf8');
function block(start, end) { const i = html.indexOf(start); const j = html.indexOf(end, i); return html.slice(i, j); }
const order = new Set([...block('const COURSE_ORDER = [', '];').matchAll(/"([^"]+)"/g)].map(m => m[1]));
function objKeys(name) { return new Set([...block('const ' + name + ' = {', '\n  };').matchAll(/"([^"]+)"\s*:/g)].map(m => m[1])); }
const colors = objKeys('COURSE_COLORS'), coords = objKeys('COURSE_COORDS'), tags = objKeys('COURSE_TAGS');
console.log('counts: order', order.size, 'colors', colors.size, 'coords', coords.size, 'tags', tags.size);
let ok = true;
function cmp(s, n) { for (const k of order) if (!s.has(k)) { ok = false; console.log(`  MISSING in ${n}: ${k}`); } for (const k of s) if (!order.has(k)) { ok = false; console.log(`  EXTRA in ${n}: ${k}`); } }
cmp(colors, 'colors'); cmp(coords, 'coords'); cmp(tags, 'tags');
console.log(ok ? 'ALL 4 MAPS CONSISTENT' : 'INCONSISTENT');
process.exit(ok ? 0 : 1);
