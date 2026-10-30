const fs=require('node:fs');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
execFileSync(process.execPath,[require.resolve('tailwindcss/lib/cli.js'),'-c','tailwind.config.cjs','-i','static/tailwind.input.css','-o','static/vendor/tailwind.css','--minify'],{cwd:root,stdio:'inherit'});
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?walk(path.join(dir,entry.name)):[path.join(dir,entry.name)]);}
const assets=walk(path.join(root,'static/vendor')).filter(p=>!p.endsWith('precache.js')&&!/LICENSE/i.test(p)).map(p=>'/'+path.relative(root,p).split(path.sep).join('/'));
fs.writeFileSync(path.join(root,'static/vendor/precache.js'),'self.DESKTOP_ASSETS = '+JSON.stringify(assets,null,2)+';\n');
console.log('Built local interface assets:',assets.length);
