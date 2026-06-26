import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "AI Tools | TotalSoft" };

// Inline script runs synchronously as the browser parses the <head>,
// before any JS bundle is downloaded — the earliest possible moment.
const fetchPatchScript = `(function(){
  var o=window.fetch.bind(window);
  window.fetch=function(input,init){
    if(init&&init.headers){
      var e=[];
      if(Array.isArray(init.headers)){
        e=init.headers;
      } else if(typeof init.headers.entries==='function'){
        var it=init.headers.entries(),r;
        while(!(r=it.next()).done) e.push(r.value);
      } else {
        var ks=Object.keys(init.headers);
        for(var ki=0;ki<ks.length;ki++) e.push([ks[ki],init.headers[ks[ki]]]);
      }
      var c={};
      for(var i=0;i<e.length;i++){
        var k=e[i][0],v=String(e[i][1]),cv='';
        for(var j=0;j<v.length;j++){
          if(v.charCodeAt(j)<=255){cv+=v[j];}
          else{console.warn('[fetch-patch] removed U+'+v.charCodeAt(j).toString(16)+' from header "'+k+'"');}
        }
        c[k]=cv;
      }
      init=Object.assign({},init,{headers:c});
    }
    return o(input,init);
  };
})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ro">
      <head>
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script dangerouslySetInnerHTML={{ __html: fetchPatchScript }} />
      </head>
      <body className="min-h-screen bg-white text-slate-800 text-sm">
        {children}
      </body>
    </html>
  );
}
