/* Local interface icons. Content and class logos are never rewritten. */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.WhisperIcons=api;
})(typeof globalThis==='object'?globalThis:this,function(){
 'use strict';
 const paths={
  "info": "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M12 11v6M12 7h.01\"/>",
  "warning": "<path d=\"m12 3 10 18H2zM12 9v5M12 17h.01\"/>",
  "check": "<path d=\"m5 12 4 4L19 6\"/>",
  "close": "<path d=\"m6 6 12 12M18 6 6 18\"/>",
  "settings": "<path d=\"M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1\"/><circle cx=\"12\" cy=\"12\" r=\"6\"/><circle cx=\"12\" cy=\"12\" r=\"2\"/>",
  "cloud": "<path d=\"M7 18a5 5 0 1 1 1-9 6 6 0 0 1 11 2 3.5 3.5 0 0 1 0 7z\"/>",
  "lock": "<rect x=\"5\" y=\"10\" width=\"14\" height=\"11\" rx=\"2\"/><path d=\"M8 10V7a4 4 0 0 1 8 0v3M12 14v3\"/>",
  "lightbulb": "<path d=\"M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0l-1 2H9z\"/>",
  "star": "<path d=\"m12 3 2.8 5.6L21 9.5l-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.5l6.2-.9z\"/>",
  "graduation": "<path d=\"m2 9 10-5 10 5-10 5zM6 11v6c4 3 8 3 12 0v-6M22 9v8\"/>",
  "briefcase": "<rect x=\"3\" y=\"7\" width=\"18\" height=\"14\" rx=\"2\"/><path d=\"M8 7V3h8v4M3 12c6 4 12 4 18 0M12 12v4\"/>",
  "search": "<circle cx=\"10.5\" cy=\"10.5\" r=\"6.5\"/><path d=\"m16 16 5 5\"/>",
  "target": "<circle cx=\"12\" cy=\"12\" r=\"9\"/><circle cx=\"12\" cy=\"12\" r=\"5\"/><circle cx=\"12\" cy=\"12\" r=\"1\"/>",
  "clipboard": "<rect x=\"5\" y=\"5\" width=\"14\" height=\"16\" rx=\"2\"/><rect x=\"9\" y=\"3\" width=\"6\" height=\"4\" rx=\"1\"/><path d=\"M9 12h6m-6 4h6\"/>",
  "process": "<path d=\"M4 6h16M4 12h16M4 18h16\"/><circle cx=\"8\" cy=\"6\" r=\"2\"/><circle cx=\"16\" cy=\"12\" r=\"2\"/><circle cx=\"10\" cy=\"18\" r=\"2\"/>",
  "mic": "<rect x=\"9\" y=\"2\" width=\"6\" height=\"12\" rx=\"3\"/><path d=\"M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8\"/>",
  "headphones": "<path d=\"M4 15v-3a8 8 0 0 1 16 0v3\"/><rect x=\"3\" y=\"12\" width=\"4\" height=\"8\" rx=\"2\"/><rect x=\"17\" y=\"12\" width=\"4\" height=\"8\" rx=\"2\"/>",
  "folder": "<path d=\"M3 7V4h6l3 3h9v13H3z\"/>",
  "music": "<path d=\"M9 18V5l12-2v13M9 9l12-2\"/><ellipse cx=\"6\" cy=\"18\" rx=\"3\" ry=\"3\"/><ellipse cx=\"18\" cy=\"16\" rx=\"3\" ry=\"3\"/>",
  "clock": "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M12 6v6l4 2\"/>",
  "refresh": "<path d=\"M20 7V3m0 4h-4M4 17v4m0-4h4M20 7A8 8 0 0 0 5 6M4 17a8 8 0 0 0 15 1\"/>",
  "file": "<path d=\"M14 3H5v18h14V8zM14 3v5h5M8 12h8M8 16h8\"/>",
  "users": "<circle cx=\"9\" cy=\"8\" r=\"3\"/><path d=\"M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M17 15a5 5 0 0 1 4 5\"/>",
  "book": "<path d=\"M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1zm0 0v15\"/>",
  "download": "<path d=\"M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5\"/>",
  "upload": "<path d=\"M12 15V3m-5 5 5-5 5 5M4 16v5h16v-5\"/>",
  "trash": "<path d=\"M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7\"/>",
  "map": "<path d=\"m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2zm6-2v16m6-14v16\"/>",
  "crown": "<path d=\"m3 5 4 5 5-7 5 7 4-5-3 13H6zM6 21h12\"/>",
  "shield": "<path d=\"m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6z\"/>",
  "paw": "<ellipse cx=\"12\" cy=\"16\" rx=\"5\" ry=\"4\"/><ellipse cx=\"5\" cy=\"10\" rx=\"2\" ry=\"3\"/><ellipse cx=\"10\" cy=\"6\" rx=\"2\" ry=\"3\"/><ellipse cx=\"16\" cy=\"6\" rx=\"2\" ry=\"3\"/><ellipse cx=\"20\" cy=\"11\" rx=\"2\" ry=\"3\"/>",
  "swords": "<path d=\"m3 3 12 12M21 3 9 15M4 16l4 4m8-4-4 4M3 21l3-3m15 3-3-3M3 3l1 5 4-4zm18 0-1 5-4-4z\"/>",
  "key": "<circle cx=\"8\" cy=\"8\" r=\"5\"/><path d=\"m12 12 9 9m-3-3 3-3m-6 0 3-3\"/>",
  "eye": "<path d=\"M2 12c5-9 15-9 20 0-5 9-15 9-20 0z\"/><circle cx=\"12\" cy=\"12\" r=\"3\"/>",
  "eye-off": "<path d=\"m3 3 18 18M9 5c5-1 10 1 13 7a19 19 0 0 1-4 5M6 6a20 20 0 0 0-4 6c4 7 10 9 16 5M10 10a3 3 0 0 0 4 4\"/>",
  "save": "<path d=\"M4 3h12l5 5v13H3V3zM7 3v6h9V3M7 21v-8h10v8\"/>",
  "link": "<path d=\"M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71\"/>",
  "edit": "<path d=\"m4 16 12-12 4 4L8 20l-5 1zM13 7l4 4\"/>",
  "plus": "<path d=\"M12 4v16M4 12h16\"/>",
  "record": "<circle cx=\"12\" cy=\"12\" r=\"7\"/><circle cx=\"12\" cy=\"12\" r=\"3\" fill=\"currentColor\" stroke=\"none\"/>",
  "calendar": "<rect x=\"3\" y=\"5\" width=\"18\" height=\"16\" rx=\"2\"/><path d=\"M7 3v4m10-4v4M3 11h18\"/>",
  "message": "<path d=\"M3 4h18v13H9l-6 4zM7 8h10M7 12h6\"/>",
  "compass": "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"m16 8-3 5-5 3 3-5z\"/>",
  "pin": "<path d=\"M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0z\"/><circle cx=\"12\" cy=\"10\" r=\"2\"/>",
  "gem": "<path d=\"m3 8 4-5h10l4 5-9 13zM3 8h18M7 3l5 18 5-18\"/>",
  "back": "<path d=\"m10 5-7 7 7 7M3 12h18\"/>",
  "leaf": "<path d=\"M20 3C7 3 2 7 4 15c8 7 16-1 16-12zM4 21 16 9\"/>",
  "tool": "<path d=\"M14 4a6 6 0 0 0-6 8l-5 6 3 3 6-5a6 6 0 0 0 8-6l-4 3-4-4z\"/>",
  "number": "<path d=\"m9 3-3 18M18 3l-3 18M3 9h18M2 15h18\"/>"
};
 function markup(name){
  const drawing=Object.prototype.hasOwnProperty.call(paths,name)?paths[name]:paths.info;
  return '<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'+drawing+'</svg>';
 }
 function set(element,name){
  if(!element)return;
  element.innerHTML=markup(name);
 }
 function mount(root){
  for(const element of root.querySelectorAll('[data-ui-icon]')){
   const name=element.getAttribute('data-ui-icon');
   if(element.dataset.uiIconRendered===name)continue;
   set(element,name);element.dataset.uiIconRendered=name;
  }
 }
 return {markup,set,mount};
});
