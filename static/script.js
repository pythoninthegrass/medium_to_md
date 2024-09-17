document.body.addEventListener('htmx:afterSwap', function (event) {
  if (event.detail.target.id === 'result') {
    document.querySelector('#result').scrollIntoView({ behavior: 'smooth' });
  }
});
