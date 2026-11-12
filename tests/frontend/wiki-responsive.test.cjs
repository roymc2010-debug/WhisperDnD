const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const {pathToFileURL} = require('node:url');
const {spawnSync} = require('node:child_process');

// Opt in to real layout checks; npm test otherwise stays browser-independent.
// WHISPER_BROWSER_TESTS=1 node --test tests/frontend/wiki-responsive.test.cjs
const enabled = process.env.WHISPER_BROWSER_TESTS === '1';
const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

function fixture({desktop=true}={}) {
  const context = vm.createContext({console, marked:require('../../static/vendor/marked.umd.js')});
  context.window = context;
  vm.runInContext(read('static/js/utils.js'), context);
  vm.runInContext(read('static/js/wiki.js'), context);
  const categoryRenderer=context.renderWikiCategoryPills.toString();
  const dossier = context.buildSessionDossierHtml({session_number:4,title:'Prueba de lectura',
    chronicle_markdown:'## Compañía de aventureros\n\n'+
      '| Personaje | Jugador / Rol | Clase / Especie | Rol en la sesión |\n'+
      '| --- | --- | --- | --- |\n'+
      '| Markus Veyl | Roy | Guerrero / Humano | Permaneció en guardia sobre la cubierta del navío mercante coordinando el cierre del interludio marítimo. |\n'+
      '| Atou Shadowgrace | IDarkLink | Monje / Elfo | Montó guardia junto a sus compañeros esperando la llegada al muelle del puerto. |\n\n'+
      'Texto de prueba para la lectura de una crónica larga.\n\n'.repeat(45),
    raw_transcript:'Una transcripción de prueba.\nOtra intervención de la mesa.'});
  let html = read('static/index.html').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<link\b[^>]*rel="stylesheet"[^>]*>/gi, '');
  const css = ['static/vendor/tailwind.css','static/styles.css','static/desktop.css']
    .map(read).join('\n').replaceAll("url('/static/", "url('"+pathToFileURL(path.join(root,'static/')).href);
  html = html.replace('</head>', '<style>'+css+'</style></head>');
  const setup = `
    window.currentActiveView='wiki';
    document.querySelectorAll('main>section').forEach(s=>s.classList.toggle('hidden',s.id!=='viewWiki'));
    for(const id of ['viewWiki','wikiExplorerLayout','wikiDossierContent'])document.getElementById(id).classList.remove('hidden');
    for(const id of ['wikiEmptyCampaignState','wikiDossierEmpty'])document.getElementById(id).classList.add('hidden');
    document.getElementById('wikiDossierContent').innerHTML=${JSON.stringify(dossier)};
    document.getElementById('wikiEntityList').innerHTML='<button>Sesión 4: prueba de lectura</button>';
    (()=>{
      const currentWikiCampaignState={quests:Array(10).fill({}),npcs:Array(15).fill({}),universal_pcs:Array(6).fill({}),locations:Array(9).fill({}),items:Array(21).fill({}),sessions:Array(5).fill({})};
      const activeWikiCategory='quests';
      (${categoryRenderer})();
    })();
    document.getElementById('wikiCampaignSelect').innerHTML='<option>Los mapas olvidados y el archipiélago del norte (5 sesiones)</option>';
    document.getElementById('wikiSessionExportSelect').innerHTML='<option value="5">Sesión #5 (Última): Interludio en Alta Mar y Despedida en Cubierta</option>';
    window.onload=async()=>{
      await document.fonts.ready;
      const tab=document.getElementById('wikiSessionChronicleTab');
      const broken=[];
      for(const cell of tab.querySelectorAll('th:not(:last-child),td:not(:last-child)')){
        const walker=document.createTreeWalker(cell,NodeFilter.SHOW_TEXT);
        let text;
        while(text=walker.nextNode())for(const word of text.textContent.matchAll(/\\S+/g)){
          const range=document.createRange();range.setStart(text,word.index);range.setEnd(text,word.index+word[0].length);
          if(new Set([...range.getClientRects()].map(r=>Math.round(r.top))).size>1)broken.push(word[0]);
        }
      }
      const dossier=document.getElementById('wikiDossierColumn');
      const scrollsY=el=>el.scrollHeight>el.clientHeight+1&&['auto','scroll'].includes(getComputedStyle(el).overflowY);
      const table=tab.querySelector('table');
      const main=document.querySelector('main');
      const header=document.getElementById('wikiHeaderCard');
      const downloadButton=document.getElementById('wikiDownloadButton');
      const downloadMenu=document.getElementById('wikiDownloadMenu');
      let downloads={available:false};
      if(downloadButton&&downloadMenu){
        let toggled=new Promise(resolve=>downloadMenu.addEventListener('toggle',resolve,{once:true}));
        downloadButton.click();await toggled;
        const rect=downloadMenu.getBoundingClientRect();
        downloads={available:true,label:downloadButton.textContent.trim(),open:downloadMenu.matches(':popover-open'),
          choices:[...downloadMenu.querySelectorAll('button')].filter(b=>b.getBoundingClientRect().width>0).length,
          explanations:downloadMenu.querySelectorAll('.wiki-download-description').length,
          fits:rect.left>=0&&rect.right<=innerWidth&&rect.top>=0&&rect.bottom<=innerHeight};
        toggled=new Promise(resolve=>downloadMenu.addEventListener('toggle',resolve,{once:true}));
        downloadButton.click();await toggled;
        downloads.closed=!downloadMenu.matches(':popover-open');
      }
      const mainTop=main.scrollTop,headerTop=header.getBoundingClientRect().top;
      dossier.scrollTop=160;
      const sessionScrollIndependent=dossier.scrollTop>0&&main.scrollTop===mainTop&&header.getBoundingClientRect().top===headerTop;
      dossier.scrollTop=0;
      const metrics={width:innerWidth,brokenWords:broken,dossierScrolls:scrollsY(dossier),sessionScrollIndependent,
        downloads,
        headerHeight:header.getBoundingClientRect().height,runtimeErrors:window.__layoutErrors||[],
        managementInHeader:header.contains(document.getElementById('btnMyCampaigns'))&&header.contains(document.getElementById('btnImportCampaign')),
        headerActions:[...header.querySelectorAll('button')].filter(b=>b.getBoundingClientRect().width>0).length,
        articleScrolls:scrollsY(tab),mainScrolls:scrollsY(main),
        pageOverflows:document.documentElement.scrollWidth>innerWidth+1||main.scrollWidth>main.clientWidth+1,
        clippedCategories:[...document.querySelectorAll('#wikiCategoryFilters button>span:not([id])')].filter(s=>s.scrollWidth>s.clientWidth+1).map(s=>s.textContent),
        tableScrolls:table.scrollWidth>table.clientWidth+1&&getComputedStyle(table).overflowX==='auto',
        filters:[...document.querySelectorAll('#wikiCategoryFilters button')].filter(b=>b.getBoundingClientRect().width>0).length};
      window.__wikiLayoutMetrics=metrics;
      const result=document.createElement('pre');result.id='layout-result';result.hidden=true;
      result.textContent=JSON.stringify(metrics);document.body.appendChild(result);
    };`;
  const desktopScripts=['static/js/ui-icons.js','static/js/desktop-core.js',...(desktop?['static/js/desktop.js']:[])]
    .map(file=>'<script src="'+pathToFileURL(path.join(root,file)).href+'"></script>').join('');
  const errors='<script>window.__layoutErrors=[];window.addEventListener("error",e=>window.__layoutErrors.push(e.message));</script>';
  return html.replace('</body>', errors+desktopScripts+'<script>'+setup+'</script></body>');
}

function verifyLayout({desktop=true,widths=[1536,1280,1024,768,520]}={}) {
  const browser = process.env.WHISPER_BROWSER_BINARY || [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/chromium','/usr/bin/google-chrome'
  ].find(p=>fs.existsSync(p));
  assert.ok(browser,'Set WHISPER_BROWSER_BINARY to an installed Chromium browser');
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'whisper-wiki-layout-'));
  try {
    const file=path.join(temp,'wiki.html');fs.writeFileSync(file,fixture({desktop}));
    // Chromium's Windows headless window has a minimum outer width of about 520px.
    for(const width of widths){
      const result=spawnSync(browser,['--headless=new','--no-first-run','--no-default-browser-check',
        '--disable-extensions','--disable-background-networking','--hide-scrollbars',
        '--user-data-dir='+path.join(temp,'profile-'+width),'--window-size='+width+',900',
        '--virtual-time-budget=2000','--dump-dom',pathToFileURL(file).href],
        {encoding:'utf8',windowsHide:true,timeout:25000,maxBuffer:4*1024*1024});
      assert.ifError(result.error);
      const match=result.stdout.match(/<pre id="layout-result"[^>]*>([^<]+)<\/pre>/);
      assert.ok(match,'Browser did not finish the layout fixture: '+result.stderr.slice(-600));
      const metrics=JSON.parse(match[1].replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>'));
      console.log(JSON.stringify(metrics));
      assert.deepEqual(metrics.runtimeErrors,[],width+': desktop initialization must finish without errors');
      assert.deepEqual(metrics.brokenWords,[],width+': names and headings must break at word boundaries');
      assert.equal(metrics.dossierScrolls,metrics.width>1100,width+': desktop dossier must have its own vertical reader');
      assert.equal(metrics.sessionScrollIndependent,metrics.width>1100,width+': reading a desktop session must leave the header and page in place');
      assert.equal(metrics.articleScrolls,false,width+': chronicle must not introduce another vertical reader');
      if(metrics.width<=1100)assert.equal(metrics.mainScrolls,true,width+': narrow windows use the page for reading');
      assert.equal(metrics.pageOverflows,false,width+': wide tables must not overflow the page');
      assert.equal(metrics.filters,6,width+': all Wiki categories must remain available');
      assert.deepEqual(metrics.clippedCategories,[],width+': loaded campaign category labels must remain readable');
      assert.equal(metrics.managementInHeader,true,width+': campaign tools belong beside the campaign, without an extra toolbar');
      assert.equal(metrics.headerActions,5,width+': campaign tools, refresh, one Download button and Drive remain available');
      assert.equal(metrics.downloads.available,true,width+': Download opens the document choices');
      assert.equal(metrics.downloads.label,'Descargar');
      assert.equal(metrics.downloads.open,true);
      assert.equal(metrics.downloads.choices,3);
      assert.equal(metrics.downloads.explanations,3);
      assert.equal(metrics.downloads.fits,true,width+': download choices must stay inside the viewport');
      assert.equal(metrics.downloads.closed,true);
      if(width>=1280)assert.ok(metrics.headerHeight<=200,width+': the header must leave room for reading the Wiki');
      if(width===520)assert.equal(metrics.tableScrolls,true,width+': a narrow table must scroll locally');
    }
  } finally {
    assert.equal(path.dirname(temp),path.resolve(os.tmpdir()));
    assert.ok(path.basename(temp).startsWith('whisper-wiki-layout-'));
    fs.rmSync(temp,{recursive:true,force:true,maxRetries:5,retryDelay:200});
  }
}

test('Wiki scrolls desktop sessions independently and preserves natural page reading in narrow windows', {skip:!enabled}, () => verifyLayout());
test('Wiki header stays compact and complete even when desktop setup has not run', {skip:!enabled}, () => verifyLayout({desktop:false,widths:[1536,768,520]}));
