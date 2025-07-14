const fs = require('fs');
const html = fs.readFileSync('templates/index.html', 'utf8');
let divCount = 0;
let navCount = 0;
const lines = html.split('\n');
lines.forEach((line, i) => {
  const opDiv = (line.match(/<div/g) || []).length;
  const clDiv = (line.match(/<\/div>/g) || []).length;
  divCount += opDiv - clDiv;
  if(divCount < 0) console.log(`div unbalanced at line ${i+1}: ${line.trim()}`);
});
console.log("Final div balance: " + divCount);
