(function () {
    "use strict";

    $("[data-toggle='offcanvas']").click(function () {
        $(".row-offcanvas").toggleClass("active");
    });

    // namespace for the program
    var dart = {};

    // expose all the functions here under the window.dart
    window.dart = dart;
    return window.dart;
})();
