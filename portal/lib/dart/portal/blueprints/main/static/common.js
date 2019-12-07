/* global dart, moment */
(function() {
    "use strict";

    dart.message = function (title, body, clazz) {
        var modal_html = [
            "<div id='dialog' class='modal' tabindex='-1' role='dialog'>",
                "<div class='modal-dialog' role='document'>",
                    "<div class='modal-content'>",
                        "<div class='modal-header " + clazz + "'>",
                            "<h5 class='modal-title'>" + title + "</h5>",
                            "<button type='button' class='close' data-dismiss='modal' aria-label='Close'>",
                                "<span aria-hidden='true'>&times;</span>",
                            "</button>",
                        "</div>",
                        "<div class='modal-body'>",
                            "<p>" + body + "</p>",
                        "</div>",
                        "<div class='modal-footer'>",
                            "<button type='button' class='btn btn-secondary' data-dismiss='modal'>Close</button>",
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
            return "<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>" + data + " <span class='fas fa-exclamation' aria-hidden='true'></span></span>";
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
                name = row.name ? row.name : dart.name;
            results.push("<div>" + data + "</div>");
            if (!row.environment && dart.ignore.indexOf(name) === -1) {
                results.push("<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>process not assigned to host</span>");
            }
            if (row.error) {
                results.push("<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>" + row.error + "</span>");
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
                results.push("<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>invalid schedule <span class='fas fa-exclamation' aria-hidden='true'></span></span>");
            }
            return results.join("");
        } else {
            if (row.daemon) {
                if (row.state !== "RUNNING") {
                    return "<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>daemon is not online</span>";
                } else {
                    return "<span class='alert-success' style='background-color: transparent; font-weight: bold;'>daemon online</span>";
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
                results.push("<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>invalid schedule <span class='fas fa-exclamation' aria-hidden='true'></span></span>");
            }
            return results.join("");
        } else {
            return "-";
        }
    };

    dart.format_disabled = function (data) {
        if (data) {
            return "<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>DISABLED</span>";
        } else {
            return "<span class='alert-success' style='background-color: transparent; font-weight: bold;'>ENABLED</span>";
        }
    };

    dart.format_active_state = function (data) {
        if (data) {
            if (data === "RUNNING") {
                return "<span class='alert-success' style='background-color: transparent; font-weight: bold;'>" + data + "</span>";

            } else if (data === "STARTING" || data === "STOPPED" || data === "STOPPING" || data === "EXITED") {
                return "<span class='alert-warning' style='background-color: transparent; font-weight: bold;'>" + data + "</span>";
            } else {
                return "<span class='alert-danger' style='background-color: transparent; font-weight: bold;'>" + data + "</span>";
            }
        } else {
            return "-";
        }
    };

    dart.format_pending_state = function (data) {
        return "waiting to be " + data;
    };

    dart.format_active_actions = function (data, row) {
        var actions = [],
            name = row.name ? row.name : dart.name;

        if (dart.ignore.indexOf(name) !== -1) {
            // can't do anything to dart from this panel
            return "";
        }

        actions = [
            "<div class='dropdown'>",
                "<button class='btn btn-primary dropdown-toggle' type='button' data-toggle='dropdown' aria-haspopup='true' aria-expanded='false'>Action</button>",
                "<div class='dropdown-menu dropdown-menu-right'>",
                    "<a href='javascript:void(0);' class='dropdown-item start'>Start</a>",
                    "<a href='javascript:void(0);' class='dropdown-item stop'>Stop</a>",
                    "<a href='javascript:void(0);' class='dropdown-item restart'>Restart</a>",
                    "<div class='dropdown-divider'></div>",
                    "<a href='javascript:void(0);' class='dropdown-item enable'>Enable</a>",
                    "<a href='javascript:void(0);' class='dropdown-item disable'>Disable</a>",
                "</div>",
            "</div>",
        ];
        return "<div class='text-center text-nowrap'>" + actions.join("") + "</div>";
    };

    dart.format_pending_actions = function () {
        var actions = [
            "<div class='dropdown'>",
                "<button class='btn btn-primary dropdown-toggle' type='button' data-toggle='dropdown' aria-haspopup='true' aria-expanded='false'>Action</button>",
                "<div class='dropdown-menu dropdown-menu-right'>",
                    "<a href='javascript:void(0);' class='dropdown-item update'>Update</a>",
                    "<div class='dropdown-divider'></div>",
                    "<a href='javascript:void(0);' class='dropdown-item enable'>Enable</a>",
                    "<a href='javascript:void(0);' class='dropdown-item disable'>Disable</a>",
                "</div>",
            "</div>",
        ];
        return "<div class='text-center text-nowrap'>" + actions.join("") + "</div>";
    };

    dart.format_assigned_actions = function () {
        var actions = [
            "<div class='dropdown'>",
                "<button class='btn btn-secondary btn-sm dropdown-toggle' type='button' data-toggle='dropdown' aria-haspopup='true' aria-expanded='false'>Action</button>",
                "<div class='dropdown-menu dropdown-menu-right'>",
                    "<a href='javascript:void(0);' class='dropdown-item unassign'>Unassign</a>",
                    "<div class='dropdown-divider'></div>",
                    "<a href='javascript:void(0);' class='dropdown-item start'>Start</a>",
                    "<a href='javascript:void(0);' class='dropdown-item stop'>Stop</a>",
                    "<a href='javascript:void(0);' class='dropdown-item restart'>Restart</a>",
                    "<div class='dropdown-divider'></div>",
                    "<a href='javascript:void(0);' class='dropdown-item enable'>Enable</a>",
                    "<a href='javascript:void(0);' class='dropdown-item disable'>Disable</a>",
                "</div>",
            "</div>",
        ];
        return "<div class='text-center text-nowrap'>" + actions.join("") + "</div>";
    };

    dart.column_active_actions = {
        "click a.start": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_start(dart.action, fqdn, process_name);
        },
        "click a.stop": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_stop(dart.action, fqdn, process_name);
        },
        "click a.restart": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_restart(dart.action, fqdn, process_name);
        },
        "click a.enable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_enable(dart.action, fqdn, process_name);
        },
        "click a.disable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_disable(dart.action, fqdn, process_name);
        }
    };

    dart.column_pending_actions = {
        "click a.update": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_update(dart.action, fqdn, process_name);
        },
        "click a.enable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_enable(dart.action, fqdn, process_name);
        },
        "click a.disable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_disable(dart.action, fqdn, process_name);
        }
    };

    dart.column_assigned_actions = {
        "click a.unassign": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_unassign(dart.action, fqdn, process_name);
        },
        "click a.start": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_start(dart.action, fqdn, process_name);
        },
        "click a.stop": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_stop(dart.action, fqdn, process_name);
        },
        "click a.restart": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_restart(dart.action, fqdn, process_name);
        },
        "click a.enable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_enable(dart.action, fqdn, process_name);
        },
        "click a.disable": function (e, value, row) {
            var fqdn = row.fqdn ? row.fqdn : dart.fqdn,
                process_name = row.name ? row.name : dart.process_name;
            dart.command_disable(dart.action, fqdn, process_name);
        }
    };

    dart.send_command = function (endpoint, params, success, failure) {
        $.ajax({
            url: endpoint,
            method: "POST",
            data: params
        }).done(function () {
            dart.message("Done", success);
            dart.refresh();
        }).fail(function (jqXHR) {
            var error = jqXHR.responseJSON.message;
            if (!error) { error = "uknown error"; }
            dart.message("Error", failure + error, "alert-danger");
        });
    };

    dart.command_reread = function (endpoint, fqdn) {
        dart.send_command(
            endpoint,
            { action: "reread", fqdn: fqdn },
            "Sent reread command to " + fqdn + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + ": "
        );
    };

    dart.command_rewrite = function (endpoint, fqdn) {
        dart.send_command(
            endpoint,
            { action: "rewrite", fqdn: fqdn },
            "Sent rewrite command to " + fqdn + ". Configurations should be updated soon. Note that a rewrite implies a reread. No separate reread is necessary.",
            "Problem encountered when sending command to " + fqdn + ": "
        );
    };

    dart.command_start = function (endpoint, fqdn, process_name) {
        dart.send_command(
            endpoint,
            { action: "start", "fqdn": fqdn, "process_name": process_name },
            "Sent start command to " + fqdn + " for " + process_name + ". The process should be started soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process_name + ": "
        );
    };

    dart.command_stop = function (endpoint, fqdn, process_name) {
        dart.send_command(
            endpoint,
            { action: "stop", "fqdn": fqdn, "process_name": process_name },
            "Sent stop command to " + fqdn + " for " + process_name + ". The process should be stopped soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process_name + ": "
        );
    };

    dart.command_restart = function (endpoint, fqdn, process_name) {
        dart.send_command(
            endpoint,
            { action: "restart", "fqdn": fqdn, "process_name": process_name },
            "Sent restart command to " + fqdn + " for " + process_name + ". The process should be restarted soon.", 
            "Problem encountered when sending command to " + fqdn + " for " + process_name + ": "
        );
    };

    dart.command_update = function (endpoint, fqdn, process_name) {
        dart.send_command(
            endpoint,
            { action: "update", "fqdn": fqdn, "process_name": process_name },
            "Sent update command to " + fqdn + " for " + process_name + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process_name + ": "
        );
    };

    dart.command_enable = function (endpoint, fqdn, process_name) {
        dart.send_command(
            endpoint,
            { action: "enable", "fqdn": fqdn, "process_name": process_name },
            "Sent enable command to " + fqdn + " for " + process_name + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process_name + ": "
        );
    };

    dart.command_disable = function (endpoint, fqdn, process_name) {
        dart.send_command(
            endpoint,
            { action: "disable", "fqdn": fqdn, "process_name": process_name },
            "Sent disable command to " + fqdn + " for " + process_name + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process_name + ": "
        );
    };

    dart.command_assign = function (endpoint, fqdn, process_name, process_environment) {
        dart.send_command(
            endpoint,
            { action: "assign", "fqdn": fqdn, "process_name": process_name, "process_environment": process_environment },
            "Assigned " + process_name + " " + process_environment + " to " + process_name + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process_name + " " + process_environment + ": "
        );
    };

    dart.command_unassign = function (endpoint, fqdn, process_name) {
        dart.send_command(
            endpoint,
            { action: "unassign", "fqdn": fqdn, "process_name": process_name },
            "Unassigned " + process_name + " from " + fqdn + ". Configurations should be updated soon.",
            "Problem encountered when sending command to " + fqdn + " for " + process_name + ": "
        );
    };

    dart.refresh = function () {
        // update all of the tables
        $("#active-table").bootstrapTable("refresh", {silent: true});
        $("#pending-table").bootstrapTable("refresh", {silent: true});
        $("#assigned-table").bootstrapTable("refresh", {silent: true});
    };

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
})();
