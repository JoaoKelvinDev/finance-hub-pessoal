// Aplica o tema antes da pintura para evitar flash. Arquivo separado (não inline) para a
// política de segurança de conteúdo (CSP) poder proibir scripts inline.
try {
  var t = localStorage.getItem('fh-theme') || 'system'
  var dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
} catch (e) {}
