/* Shared presentation decisions; no campaign data or provider access. */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports) module.exports=api;
 else root.WhisperDesktopCore=api;
})(typeof globalThis==='object'?globalThis:this,function(){
 'use strict';
 const themes=[
  {
    "id": "copper",
    "name": "Grafito y cobre",
    "mode": "dark",
    "canvas": "#171717",
    "surface": "#202020",
    "raised": "#292929",
    "line": "#393939",
    "control": "#817b74",
    "text": "#f3f0eb",
    "muted": "#beb8b0",
    "accent": "#d6aa7a",
    "on-accent": "#211a14",
    "hover": "#e5bb8c",
    "pressed": "#c69a6a",
    "focus": "#f0cfaa"
  },
  {
    "id": "graphite",
    "name": "Carbón",
    "mode": "dark",
    "canvas": "#171819",
    "surface": "#202224",
    "raised": "#2b2d30",
    "line": "#3d4044",
    "control": "#838990",
    "text": "#f1f2f3",
    "muted": "#bcc1c7",
    "accent": "#c9cdd3",
    "on-accent": "#1b1d20",
    "hover": "#e0e3e7",
    "pressed": "#b0b6be",
    "focus": "#eceef1"
  },
  {
    "id": "midnight",
    "name": "Tinta azul",
    "mode": "dark",
    "canvas": "#171c25",
    "surface": "#202835",
    "raised": "#2a3444",
    "line": "#3b475b",
    "control": "#8391a8",
    "text": "#eff2f7",
    "muted": "#bcc7d8",
    "accent": "#a4bee7",
    "on-accent": "#192538",
    "hover": "#bcd1f0",
    "pressed": "#8ca8d4",
    "focus": "#d2e0f6"
  },
  {
    "id": "wine",
    "name": "Borgoña",
    "mode": "dark",
    "canvas": "#20191c",
    "surface": "#2a2226",
    "raised": "#382d32",
    "line": "#4b3c43",
    "control": "#a08b95",
    "text": "#f4edf0",
    "muted": "#cabac2",
    "accent": "#dfafb9",
    "on-accent": "#321e25",
    "hover": "#edc4cc",
    "pressed": "#cc99a5",
    "focus": "#f3d7de"
  },
  {
    "id": "paper",
    "name": "Papel y tinta",
    "mode": "light",
    "canvas": "#f4f2ed",
    "surface": "#ffffff",
    "raised": "#e9e6df",
    "line": "#d7d2c9",
    "control": "#7c776e",
    "text": "#262521",
    "muted": "#5c5850",
    "accent": "#383633",
    "on-accent": "#ffffff",
    "hover": "#504c46",
    "pressed": "#24221f",
    "focus": "#785435"
  },
  {
    "id": "sky",
    "name": "Azul claro",
    "mode": "light",
    "canvas": "#f0f3f8",
    "surface": "#ffffff",
    "raised": "#e4eaf2",
    "line": "#ccd5e1",
    "control": "#77869a",
    "text": "#232d3b",
    "muted": "#536174",
    "accent": "#35567f",
    "on-accent": "#ffffff",
    "hover": "#456b98",
    "pressed": "#274363",
    "focus": "#244f84"
  }
];
 function normalizeTheme(value){return themes.some(t=>t.id===value)?value:'copper';}
 function sessionNumbers(state){
  return [...new Set((Array.isArray(state?.sessions)?state.sessions:[])
   .map(s=>Number(s.session_number)).filter(n=>Number.isSafeInteger(n)&&n>0))].sort((a,b)=>a-b);
 }
 function validateRerecord({campaign,selectedCampaign,sessions,session,recording}){
  if(recording) return 'Detén la grabación antes de elegir otra sesión.';
  if(!campaign||campaign!==selectedCampaign) return 'La campaña cambió. Vuelve a elegir la sesión.';
  if(!Number.isSafeInteger(session)||!sessions.includes(session)) return 'Elige una sesión existente.';
  return '';
 }
 return {themes,normalizeTheme,sessionNumbers,validateRerecord};
});
