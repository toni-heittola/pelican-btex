$(document).ready(function(){
   var hash = window.location.hash.substr(1);
   $('#collapse'+hash).collapse('show');
});