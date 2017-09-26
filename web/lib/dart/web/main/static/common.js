/* global dart, moment */

(function() {
    "use strict";

    dart.message = function (title, body, clazz) {
        var modal_html = [
            "<div id='dialog' class='modal' tabindex='-1' role='dialog' aria-hidden='true'>",
                "<div class='modal-dialog'>",
                    "<div class='modal-content'>",
                        "<div class='modal-header " + clazz + "'>",
                            "<button type='button' class='close' data-dismiss='modal' aria-label='Close'><span aria-hidden='true'>&times;</span></button>",
                            "<h4 class='modal-title'>" + title + "</h4>",
                        "</div>",
                        "<div class='modal-body'>",
                            "<p>" + body + "</p>",
                        "</div>",
                        "<div class='modal-footer'>",
                            "<button class='btn btn-primary' data-dismiss='modal' aria-hidden='true'>Close</button>",
                        "</div>",
                    "</div>",
                "</div>",
            "</div>",
        ].join("");
        $("#dialog").remove();
        $("body").append(modal_html);
        $("#dialog").modal("show");
    };

    // add an element of danger to specific columns where the value is an
    // integer and is greater than zero.
    dart.format_count_danger = function (data) {
        if (data === parseInt(data, 10) && data > 0) {
            return "<span class='alert-danger' style='background: transparent; font-weight: bold;'>" + data + " <span class='glyphicon glyphicon-exclamation-sign' aria-hidden='true'></span></span>";
        }
        return data;
    };

    // some columns just need to be not wrapped
    dart.format_nowrap = function (data) {
        if (data) {
            return "<div class='text-nowrap'>" + data + "</div>";
        } else {
            return "-";
        }
    };

    dart.format_active_description = function (data, row) {
        if (data) {
            var results = [],
                process = row.process ? row.process : dart.process;
            results.push("<div>" + data + "</div>");
            if (!row.environment && dart.ignore.indexOf(process) === -1) {
                results.push("<span class='alert-danger' style='background: transparent; font-weight: bold;'>process not assigned to host</span>");
            }
            if (row.error) {
                results.push("<span class='alert-danger' style='background: transparent; font-weight: bold;'>" + row.error + "</span>");
            }
            return results.join("");
        } else {
            return "-";
        }
    };

    dart.format_active_schedule = function (data, row) {
        if (data) {
            var results = [];
            results.push("<div class='text-nowrap'><tt>" + data + "</tt></div>");
            if (row.starts) {
                var now = moment().unix(),
                    starts_timestamp = moment(row.starts).unix(),
                    delay = starts_timestamp - now;
                results.push("<div class='text-nowrap'>starts in ");
                if (delay > 86400) {
                    results.push(parseFloat(delay / 60 / 60 / 24).toFixed(1) + " days");
                } else if (delay > 3600) {
                    results.push(parseFloat(delay / 60 / 60).toFixed(1) + " hours");
                } else if (delay > 60) {
                    results.push(parseFloat(delay / 60).toFixed(0) + " minutes");
                } else {
                    results.push(delay + " seconds");
                }
                results.push("</div>");
            } else {
                results.push("<span class='alert-danger' style='background: transparent; font-weight: bold;'>invalid schedule <span class='glyphicon glyphicon-exclamation-sign' aria-hidden='true'></span></span>");
            }
            return results.join("");
        } else {
            if (row.daemon) {
                if (row.status !== "RUNNING") {
                    return "<span class='alert-danger' style='background: transparent; font-weight: bold;'>daemon is not online</span>";
                } else {
                    return "<span class='alert-success' style='background: transparent; font-weight: bold;'>daemon online</span>";
                }
            } else {
                return "-";
            }
        }
    };

    dart.format_assigned_schedule = function (data, row) {
        if (data) {
            var results = [];
            results.push("<div class='text-nowrap'><tt>" + data + "</tt></div>");
            if (row.starts) {
                var now = moment().unix(),
                    starts_timestamp = moment(row.starts).unix(),
                    delay = starts_timestamp - now;
                results.push("<div class='text-nowrap'>starts in ");
                if (delay > 86400) {
                    results.push(parseFloat(delay / 60 / 60 / 24).toFixed(1) + " days");
                } else if (delay > 3600) {
                    results.push(parseFloat(delay / 60 / 60).toFixed(1) + " hours");
                } else if (delay > 60) {
                    results.push(parseFloat(delay / 60).toFixed(0) + " minutes");
                } else {
                    results.push(delay + " seconds");
                }
                results.push("</div>");
            } else {
                results.push("<span class='alert-danger' style='background: transparent; font-weight: bold;'>invalid schedule <span class='glyphicon glyphicon-exclamation-sign' aria-hidden='true'></span></span>");
            }
            return results.join("");
        } else {
            return "-";
        }
    };

    dart.format_disabled = function (data) {
        if (data) {
            return "<span class='alert-danger' style='background: transparent; font-weight: bold;'>DISABLED</span>";
        } else {
            return "<span class='alert-success' style='background: transparent; font-weight: bold;'>ENABLED</span>";
        }
    };

    dart.format_active_status = function (data) {
        if (data) {
            if (data === "RUNNING") {
                return "<span class='alert-success' style='background: transparent; font-weight: bold;'>" + data + "</span>";

            } else if (data === "STARTING" || data === "STOPPED" || data === "STOPPING" || data === "EXITED") {
                return "<span class='alert-warning' style='background: transparent; font-weight: bold;'>" + data + "</span>";
            } else {
                return "<span class='alert-danger' style='background: transparent; font-weight: bold;'>" + data + "</span>";
            }
        } else {
            return "-";
        }
    };

    dart.format_pending_status = function (data) {
        return "waiting to be " + data;
    };

    dart.format_active_actions = function (data, row) {
        var process = row.process ? row.process : dart.process,
            actions = [];

        if (dart.ignore.indexOf(process) !== -1) {
            // can't do anything to dart from this panel
            return "";
        }

        actions = [
            "<div class='btn-group btn-group-s'>",
                "<button type='button' class='btn btn-default dropdown-toggle' data-toggle='dropdown' aria-haspopup='true' aria-expanded='false'>",
                    "Action <span class='caret'></span>",
                "</button>",
                "<ul class='dropdown-menu'>",
                    "<li><a href='#' class='start'>Start</a></li>",
                    "<li><a href='#' class='stop'>Stop</a></li>",
                    "<li><a href='#' class='restart'>Restart</a></li>",
                    "<li role='separator' class='divider'></li>",
                    "<li><a href='#' class='enable'>Enable</a></li>",
                    "<li><a href='#' class='disable'>Disable</a></li>",
                "</ul>",
            "</div>",
        ];
        return "<div class='text-center text-nowrap'>" + actions.join("") + "</div>";
    };

    dart.format_pending_actions = function () {
        var actions = [
            "<div class='btn-group btn-group-s'>",
                "<button type='button' class='btn btn-default dropdown-toggle' data-toggle='dropdown' aria-haspopup='true' aria-expanded='false'>",
                    "Action <span class='caret'></span>",
                "</button>",
                "<ul class='dropdown-menu'>",
                    "<li><a href='#' class='update'>Update</a></li>",
                    "<li role='separator' class='divider'></li>",
                    "<li><a href='#' class='add'>Add</a></li>",
                    "<li><a href='#' class='remove'>Remove</a></li>",
                    "<li role='separator' class='divider'></li>",
                    "<li><a href='#' class='enable'>Enable</a></li>",
                    "<li><a href='#' class='disable'>Disable</a></li>",
                "</ul>",
            "</div>",
        ];
        return "<div class='text-center text-nowrap'>" + actions.join("") + "</div>";
    };

    dart.format_assigned_actions = function () {
        var actions = [
            "<div class='btn-group btn-group-s'>",
                "<button type='button' class='btn btn-default dropdown-toggle' data-toggle='dropdown' aria-haspopup='true' aria-expanded='false'>",
                    "Action <span class='caret'></span>",
                "</button>",
                "<ul class='dropdown-menu'>",
                    "<li><a href='#' class='unassign'>Unassign</a></li>",
                    "<li role='separator' class='divider'></li>",
                    "<li><a href='#' class='start'>Start</a></li>",
                    "<li><a href='#' class='stop'>Stop</a></li>",
                    "<li><a href='#' class='restart'>Restart</a></li>",
                    "<li role='separator' class='divider'></li>",
                    "<li><a href='#' class='enable'>Enable</a></li>",
                    "<li><a href='#' class='disable'>Disable</a></li>",
                "</ul>",
            "</div>",
        ];
        return "<div class='text-center text-nowrap'>" + actions.join("") + "</div>";
    };

    dart.column_active_actions = {
        "click a.start": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_start(dart.endpoints.start, fqdn, process);
        },
        "click a.stop": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_stop(dart.endpoints.stop, fqdn, process);
        },
        "click a.restart": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_restart(dart.endpoints.restart, fqdn, process);
        },
        "click a.enable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_enable(dart.endpoints.enable, fqdn, process);
        },
        "click a.disable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_disable(dart.endpoints.disable, fqdn, process);
        }
    };

    dart.column_pending_actions = {
        "click a.update": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_update(dart.endpoints.update, fqdn, process);
        },
        "click a.add": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_add(dart.endpoints.add, fqdn, process);
        },
        "click a.remove": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_remove(dart.endpoints.remove, fqdn, process);
        },
        "click a.enable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_enable(dart.endpoints.enable, fqdn, process);
        },
        "click a.disable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_disable(dart.endpoints.disable, fqdn, process);
        }
    };

    dart.column_assigned_actions = {
        "click a.unassign": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_unassign(dart.endpoints.unassign, fqdn, process);
        },
        "click a.start": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_start(dart.endpoints.start, fqdn, process);
        },
        "click a.stop": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_stop(dart.endpoints.stop, fqdn, process);
        },
        "click a.restart": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_restart(dart.endpoints.restart, fqdn, process);
        },
        "click a.enable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_enable(dart.endpoints.enable, fqdn, process);
        },
        "click a.disable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process = row.process ? row.process : dart.process;
            dart.command_disable(dart.endpoints.disable, fqdn, process);
        }
    };

    dart.send_command = function (endpoint, params, success, failure) {
        $.ajax({
            url: endpoint,
            method: "GET",
            data: params
        }).done(function () {
            dart.message("Done", success, "alert-info");
        }).fail(function (jqXHR) {
            var error = jqXHR.responseJSON.error;
            if (!error) { error = "uknown error"; }
            dart.message("Error", failure + error, "alert-danger");
        });
    };

    dart.command_reread = function (endpoint, fqdn) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn },
            "Sent reread command to " + fqdn + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + ": "
        );
    };

    dart.command_rewrite = function (endpoint, fqdn) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn },
            "Sent rewrite command to " + fqdn + ". Configurations should be updated soon. Note that a rewrite implies a reread. No separate reread is necessary.",
            "Problem encountered when sending command to " + fqdn + ": "
        );
    };

    dart.command_update = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent update command to " + fqdn + " for " + process + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_add = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent add command to " + fqdn + " for " + process + ". Configurations should be updated soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_remove = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent remove command to " + fqdn + " for " + process + ". Configurations should be updated soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_enable = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent enable command to " + fqdn + " for " + process + ". Configurations should be updated soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_disable = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent disable command to " + fqdn + " for " + process + ". Configurations should be updated soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_start = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent start command to " + fqdn + " for " + process + ". The process should be started soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_stop = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent stop command to " + fqdn + " for " + process + ". The process should be stopped soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_restart = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Sent restart command to " + fqdn + " for " + process + ". The process should be restarted soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    dart.command_assign = function (endpoint, fqdn, process, environment) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process, environment: environment },
            "Assigned " + process + " " + environment + " to " + process + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process + " " + environment + ": "
        );
    };

    dart.command_unassign = function (endpoint, fqdn, process) {
        dart.send_command(
            endpoint,
            { fqdn: fqdn, process: process },
            "Unassigned " + process + " from " + fqdn + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process + ": "
        );
    };

    $("button.assign-process-host").on("click", function (e) {
        var button = $(e.currentTarget),
            process = button.data("process"),
            environment = button.data("environment"),
            modal_html = [
            "<div id='dialog' class='modal' tabindex='-1' role='dialog' aria-hidden='true'>",
                "<div class='modal-dialog'>",
                    "<div class='modal-content'>",
                        "<div class='modal-header'>",
                            "<button type='button' class='close' data-dismiss='modal' aria-label='Close'><span aria-hidden='true'>&times;</span></button>",
                            "<h4 class='modal-title'>Assign Process to Host</h4>",
                        "</div>",
                        "<div class='modal-body'><p>",
                            "<div class='alert alert-success' role='alert' style='display: none;'></div>",
                            "<div class='alert alert-danger' role='alert' style='display: none;'></div>",
                            "Choose the host on which " + process + " will be assigned:",
                            "<form id='autocomplete'>",
                                "<input type='text' required='required' class='form-control' name='fqdn' placeholder='Host' value='' autocomplete='off'/>",
                            "</form>",
                        "</p></div>",
                        "<div class='modal-footer'>",
                            "<button class='btn btn-primary assign' aria-hidden='true'>Assign</button>",
                            "<button class='btn btn-primary' data-dismiss='modal' aria-hidden='true'>Close</button>",
                        "</div>",
                    "</div>",
                "</div>",
            "</div>",
        ].join("");
        $("#dialog").remove();
        $("body").append(modal_html);

        // enable autocomplete
        $("#autocomplete input").typeahead({
            minLength: 1,
            fitToElement: true,
            items: "all",
            autoSelect: true,
            delay: 1,
            source: function (request, response) {
                $.ajax({
                    url: dart.endpoints.autocomplete.fqdn,
                    dataType: "json",
                    data: {
                        q: request
                    }
                }).done(function (data) {
                    response(data.results);
                }).fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(textStatus);
                    console.log(errorThrown);
                    response([]);
                });
            }
        });

        // make it so that the box's assign button does something
        $("#dialog button.assign").click(function () {
            var fqdn = $("#autocomplete input").val();
            if (!fqdn) {
                $("#dialog div.alert-danger").html("Please choose a host on which " + process + " will be assigned.").show();
                return;
            }

            // ajax call that thing and then update the form when we have a response
            $.ajax({
                url: dart.endpoints.assign,
                method: "GET",
                data: {
                    fqdn: fqdn,
                    process: process,
                    environment: environment
                }
            }).done(function () {
                $("#dialog div.alert-danger").hide();
                $("#dialog div.alert-success").html("The process " + process + " " + environment + " has been assigned to " + fqdn + ". The process must now be added to the host to activate it.").show();
            }).fail(function (jqXHR) {
                var error = jqXHR.responseJSON.error;
                if (!error) { error = "uknown error"; }
                $("#dialog div.alert-success").hide();
                $("#dialog div.alert-danger").html("Problem encountered while trying to add " + process + " " + environment + " to " + fqdn + ". " + error).show();
            });

            // focus on the box again
            $("#autocomplete input").focus();
        });

        // disable automatic submission on the form
        $("#autocomplete").on("submit", function() {
            $("#dialog button.assign").click();
            return false;
        });

        // show the box
        $("#dialog").modal("show");

        // focus on the input box
        $("#autocomplete input").focus();
    });

    $("button.assign-host-process").on("click", function (e) {
        var button = $(e.currentTarget),
            fqdn = button.data("fqdn"),
            modal_html = [
            "<div id='dialog' class='modal' tabindex='-1' role='dialog' aria-hidden='true'>",
                "<div class='modal-dialog'>",
                    "<div class='modal-content'>",
                        "<div class='modal-header'>",
                            "<button type='button' class='close' data-dismiss='modal' aria-label='Close'><span aria-hidden='true'>&times;</span></button>",
                            "<h4 class='modal-title'>Assign Process to Host</h4>",
                        "</div>",
                        "<div class='modal-body'><p>",
                            "<div class='alert alert-success' role='alert' style='display: none;'></div>",
                            "<div class='alert alert-danger' role='alert' style='display: none;'></div>",
                            "Choose process that will be assigned to " + fqdn + ":",
                            "<form id='autocomplete1'>",
                                "<input type='text' required='required' class='form-control' name='process' placeholder='Process' value='' autocomplete='off'/>",
                            "</form>",
                            "Choose the environment for the process that will be assigned to " + fqdn + ":",
                            "<form id='autocomplete2'>",
                                "<input type='text' required='required' class='form-control' name='environment' placeholder='Environment' value='' autocomplete='off'/>",
                            "</form>",
                        "</p></div>",
                        "<div class='modal-footer'>",
                            "<button class='btn btn-primary assign' aria-hidden='true'>Assign</button>",
                            "<button class='btn btn-primary' data-dismiss='modal' aria-hidden='true'>Close</button>",
                        "</div>",
                    "</div>",
                "</div>",
            "</div>",
        ].join("");
        $("#dialog").remove();
        $("body").append(modal_html);

        // enable autocomplete for process
        $("#autocomplete1 input").typeahead({
            minLength: 1,
            fitToElement: true,
            items: "all",
            autoSelect: true,
            delay: 1,
            source: function (request, response) {
                $.ajax({
                    url: dart.endpoints.autocomplete.process,
                    dataType: "json",
                    data: {
                        q: request
                    }
                }).done(function (data) {
                    response(data.results);
                }).fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(textStatus);
                    console.log(errorThrown);
                    response([]);
                });
            }
        });

        // enable autocomplete for the environment
        $("#autocomplete2 input").typeahead({
            minLength: 1,
            fitToElement: true,
            items: "all",
            autoSelect: true,
            delay: 1,
            source: function (request, response) {
                $.ajax({
                    url: dart.endpoints.autocomplete.environment,
                    dataType: "json",
                    data: {
                        q: request,
                        process: $("#autocomplete1 input").val()
                    }
                }).done(function (data) {
                    response(data.results);
                }).fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(textStatus);
                    console.log(errorThrown);
                    response([]);
                });
            }
        });

        // make it so that the box's assign button does something
        $("#dialog button.assign").click(function () {
            var process = $("#autocomplete1 input").val(),
                environment = $("#autocomplete2 input").val();
            if (!process) {
                $("#dialog div.alert-danger").html("Please choose a process that will be assigned to " + fqdn + ".").show();
                return;
            }
            if (!environment) {
                $("#dialog div.alert-danger").html("Please choose an environment for the process " + process + " that will be assigned to " + fqdn + ".").show();
                return;
            }

            // ajax call that thing and then update the form when we have a response
            $.ajax({
                url: dart.endpoints.assign,
                method: "GET",
                data: {
                    fqdn: fqdn,
                    process: process,
                    environment: environment
                }
            }).done(function () {
                $("#dialog div.alert-danger").hide();
                $("#dialog div.alert-success").html("The process " + process + " " + environment + " has been assigned to " + fqdn + ". The process must now be added to the host to activate it.").show();
            }).fail(function (jqXHR) {
                var error = jqXHR.responseJSON.error;
                if (!error) { error = "uknown error"; }
                $("#dialog div.alert-success").hide();
                $("#dialog div.alert-danger").html("Problem encountered while trying to add " + process + " " + environment + " to " + fqdn + ". " + error).show();
            });

            // focus on the box again
            $("#autocomplete1 input").focus();
        });

        // disable automatic submission on the forms
        $("#autocomplete1").on("submit", function() {
            $("#dialog button.assign").click();
            return false;
        });
        $("#autocomplete2").on("submit", function() {
            $("#dialog button.assign").click();
            return false;
        });

        // show the box
        $("#dialog").modal("show");

        // focus on the process input box
        $("#autocomplete1 input").focus();
    });

    // this handles all actions related to the "active" table
    $("#active-table").bootstrapTable({
        onLoadSuccess: function () {
            $("#active-count").html(this.data.length);
        },
    });

    // this handles all actions related to the "pending" table
    $("#pending-table").bootstrapTable({
        onLoadSuccess: function () {
            $("#pending-count").html(this.data.length);
        },
    });

    // this handles all actions related to the "assigned" table
    $("#assigned-table").bootstrapTable({
        onLoadSuccess: function () {
            $("#assigned-count").html(this.data.length);
        },
    });

    $("table.table").on("show.bs.dropdown", function (e) {
        var eOffset = $(e.target).offset(),
            dropdown = $(e.target).find(".dropdown-menu");
        $(e.target).data("dropdown", dropdown);

        // remove the menu from the body
        $("body").append(dropdown.detach());

        // put it on top of the window
        dropdown.css({
            "display": "block",
            "top": eOffset.top + $(e.target).outerHeight(),
            "left": eOffset.left - dropdown.outerWidth() + $(e.target).outerWidth()
        });
    });
    $("table.table").on("hide.bs.dropdown", function (e) {
        var dropdown = $(e.target).data("dropdown");
        $(e.target).append(dropdown.detach());
        dropdown.hide();
    });

    $("#tabs a").click(function (e) {
        e.preventDefault();
        $(this).tab("show");
    });
})();
