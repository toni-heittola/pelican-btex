$(document).ready(function(){
   var hash = window.location.hash.substr(1);
   console.log(hash);
   $('#collapse'+hash).collapse('show');
});