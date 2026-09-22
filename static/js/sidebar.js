(function($) {
  "use strict";

  var currentPath = window.location.pathname;

  // ── Sidebar Dropdown Accordion Toggle ──
  $(document).on("click", ".sidebar-dropdown-toggle, .sidebar .sidebar-menu > li.dropdown > a", function(e) {
    e.preventDefault();
    var $li = $(this).closest(".nav-item");
    var $sub = $li.children(".sidebar-submenu, .dropdown-menu");
    if (!$sub.length) return;

    if ($li.hasClass("open")) {
      $sub.slideUp(180, function() {
        $li.removeClass("open");
      });
    } else {
      // Close sibling open accordions
      $li.siblings(".nav-item.open").each(function() {
        var $sib = $(this);
        $sib.children(".sidebar-submenu, .dropdown-menu").slideUp(180);
        $sib.removeClass("open");
      });
      $li.addClass("open");
      $sub.slideDown(180);
    }
  });

  // ── Active Link Detection ──
  var $menu = $(".sidebar .sidebar-menu");
  var $active = null;
  var bestLen = 0;

  $menu.find("a.nav-link-item, a.submenu-link, a.sidebar-link").each(function() {
    var href = $(this).attr("href");
    if (!href || href.length < 2 || href === "#" || href.indexOf("javascript") === 0) return;

    var normHref = href.replace(/\/+$/, "");
    var normPath = currentPath.replace(/\/+$/, "");

    if (normPath === normHref) {
      $active = $(this);
      bestLen = href.length;
      return false;
    }
    if (currentPath.indexOf(href) === 0 && href.length > bestLen) {
      bestLen = href.length;
      $active = $(this);
    }
  });

  if ($active && $active.length) {
    $active.addClass("active");
    var $parentLi = $active.closest(".nav-item, .submenu-item");
    $parentLi.addClass("active actived");

    var $parentSubmenu = $active.closest(".sidebar-submenu, .dropdown-menu");
    if ($parentSubmenu.length) {
      var $parentNav = $parentSubmenu.closest(".nav-item");
      $parentNav.addClass("open");
      $parentSubmenu.css("display", "block");
    }
  }

  // ── Sidebar Toggle Button & Mobile Drawer ──
  $(document).on("click", "#sidebarToggle, #sidebar-toggle, .sidebar-toggle-btn, [data-toggle-sidebar]", function(e) {
    e.preventDefault();
    if ($(window).width() < 992) {
      var isOpen = $("body").hasClass("sidebar-open");
      $("body").toggleClass("sidebar-open");
      $(this).attr("aria-expanded", !isOpen);
    } else {
      $("body.app").toggleClass("is-collapsed");
    }
  });

  // ── Backdrop & Close Button Dismiss ──
  $(document).on("click", ".sidebar-backdrop, #sidebar-close-btn", function(e) {
    e.preventDefault();
    $("body").removeClass("sidebar-open");
    $("#sidebarToggle, .sidebar-toggle-btn").attr("aria-expanded", "false");
  });

  // ── Auto-close drawer on mobile navigation item click ──
  $(document).on("click", ".sidebar .sidebar-menu a:not(.sidebar-dropdown-toggle)", function() {
    if ($(window).width() < 992) {
      $("body").removeClass("sidebar-open");
      $("#sidebarToggle, .sidebar-toggle-btn").attr("aria-expanded", "false");
    }
  });

  // ── Keyboard accessibility (ESC to close drawer) ──
  $(document).on("keydown", function(e) {
    if (e.key === "Escape" && $("body").hasClass("sidebar-open")) {
      $("body").removeClass("sidebar-open");
      $("#sidebarToggle, .sidebar-toggle-btn").attr("aria-expanded", "false");
    }
  });

})(jQuery);
