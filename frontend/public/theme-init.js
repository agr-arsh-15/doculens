try {
  var t = localStorage.getItem('doculens-theme')
  if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) document.documentElement.classList.add('dark')
} catch {
  /* storage blocked: keep the light theme */
}
