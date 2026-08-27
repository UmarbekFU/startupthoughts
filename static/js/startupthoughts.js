/* StartupThoughts: two small enhancements, both optional.
   Everything on the site works with JavaScript switched off. */
(function () {
	"use strict";

	var base = (function () {
		var m = location.pathname.match(/^\/(es|fr|de|it|pt|ru|ar|ja|zh)(\/|$)/);
		return m ? "/" + m[1] : "";
	})();

	var index = null, pending = [];

	function load(cb) {
		if (index) { cb(index); return; }
		pending.push(cb);
		if (pending.length > 1) return;
		var x = new XMLHttpRequest();
		x.open("GET", base + "/search-index.json", true);
		x.onload = function () {
			try { index = JSON.parse(x.responseText); } catch (e) { index = { thoughts: [] }; }
			while (pending.length) pending.shift()(index);
		};
		x.onerror = function () { index = { thoughts: [] }; while (pending.length) pending.shift()(index); };
		x.send();
	}

	/* --- "random thought" really is random, on every click --- */
	var rl = document.getElementById("randomlink");
	if (rl) {
		rl.addEventListener("click", function (e) {
			e.preventDefault();
			load(function (ix) {
				var all = ix.thoughts;
				if (!all.length) { location.href = rl.getAttribute("href"); return; }
				var here = (location.pathname.match(/\/t\/(\d+)/) || [])[1];
				var pick, guard = 0;
				do { pick = all[Math.floor(Math.random() * all.length)]; }
				while (all.length > 1 && String(pick.i) === here && ++guard < 20);
				location.href = base + "/t/" + pick.i;
			});
		});
	}

	/* --- search, without sending anybody's query anywhere --- */
	var form = document.getElementById("searchform");
	if (!form) return;

	var input = document.getElementById("q"),
		out = document.getElementById("results"),
		strings = { none: "Nothing found.", one: "1 thought", many: "{n} thoughts", from: "from" };

	function fold(s) {
		s = s.toLowerCase();
		if (String.prototype.normalize) s = s.normalize("NFD").replace(/[̀-ͯ]/g, "");
		return s.replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
	}

	function escape(s) {
		return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
	}

	function score(t, terms) {
		var hay = fold(t.t + " · " + t.a + " · " + t.s), n = 0;
		for (var i = 0; i < terms.length; i++) {
			if (hay.indexOf(terms[i]) === -1) return 0;
			n += fold(t.a).indexOf(terms[i]) !== -1 ? 3 : 1;
		}
		return n;
	}

	function render(q) {
		var terms = fold(q).split(/\s+/).filter(Boolean);
		if (!terms.length) { out.innerHTML = ""; return; }
		load(function (ix) {
			var hits = [];
			for (var i = 0; i < ix.thoughts.length; i++) {
				var s = score(ix.thoughts[i], terms);
				if (s) hits.push([s, ix.thoughts[i]]);
			}
			hits.sort(function (a, b) { return b[0] - a[0] || a[1].i - b[1].i; });
			if (!hits.length) { out.innerHTML = "<p>" + strings.none + "</p>"; return; }
			var head = hits.length === 1 ? strings.one : strings.many.replace("{n}", hits.length);
			var h = "<p>" + head + "</p><ul>";
			for (var j = 0; j < hits.length; j++) {
				var t = hits[j][1], href = base + "/t/" + t.i;
				h += '<li><blockquote cite="' + href + '"><q>' +
					escape(t.t).replace(/\n{1,}/g, " <br> <br>") +
					'</q><cite><a href="' + href + '">' + escape(t.a) + "</a></cite></blockquote></li>";
			}
			out.innerHTML = h + "</ul>";
		});
	}

	form.addEventListener("submit", function (e) { e.preventDefault(); render(input.value); });

	var timer;
	input.addEventListener("input", function () {
		clearTimeout(timer);
		timer = setTimeout(function () { render(input.value); }, 120);
	});

	var q = (location.search.match(/[?&]q=([^&]*)/) || [])[1];
	if (q) { input.value = decodeURIComponent(q.replace(/\+/g, " ")); render(input.value); }
})();

/* ------------------------------------------------------------------
   add a thought: builds the entry, previews it, and hands it off.
   No backend, no account, nothing sent anywhere without a click.
   ------------------------------------------------------------------ */
(function () {
	"use strict";

	var form = document.getElementById("addform");
	if (!form) return;

	var $ = function (id) { return document.getElementById(id); },
		text = $("f_text"), original = $("f_original"), author = $("f_author"),
		source = $("f_source"), url = $("f_url"), by = $("f_by"),
		count = $("f_count"), preview = $("addpreview"), pbody = $("addpreview_body"),
		jsonBox = $("addjson"), note = $("act_note"),
		actPr = $("act_pr"), actCopy = $("act_copy"), actDl = $("act_dl"),
		repo = (form.getAttribute("data-repo") || "").trim();

	function esc(s) {
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
			.replace(/>/g, "&gt;").replace(/"/g, "&quot;");
	}

	/* same typography the build step applies, so the preview does not lie */
	function smarten(s) {
		return s
			.replace(/(\w)'(\w)/g, "$1’$2")
			.replace(/(^|[\s(\[])"/g, "$1“").replace(/"/g, "”")
			.replace(/(^|[\s(\[])'/g, "$1‘").replace(/'/g, "’");
	}

	function strip(s) {
		s = s.trim();
		/* people paste quotes with the quote marks still on */
		if (/^["“«].*["”»]$/.test(s)) s = s.slice(1, -1).trim();
		return s;
	}

	text.addEventListener("input", function () {
		count.textContent = text.value.length;
		count.parentNode.style.color = text.value.length > 400 ? "#900" : "";
	});

	function entry() {
		var e = {
			text: smarten(strip(text.value)),
			author: strip(author.value),
			source: strip(source.value),
			source_url: url.value.trim(),
			contributor: strip(by.value)
		};
		if (original.value.trim()) e.original = original.value.trim();
		return e;
	}

	function validate() {
		var bad = [];
		[[text, "the thought"], [author, "who said it"],
		 [source, "where they said it"], [by, "your name"]].forEach(function (p) {
			p[0].classList.toggle("bad", !p[0].value.trim());
			if (!p[0].value.trim()) bad.push(p[1]);
		});
		if (strip(text.value).length > 400) bad.push("something shorter. 400 characters is the ceiling");
		return bad;
	}

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		var bad = validate();
		if (bad.length) {
			note.textContent = "";
			preview.hidden = true;
			alert("Still needed:\n\n• " + bad.join("\n• "));
			return;
		}

		var d = entry();
		pbody.innerHTML =
			'<blockquote><q>' + esc(d.text) + "</q>" +
			(d.original ? '<p class="original">' + esc(d.original) + "</p>" : "") +
			"<cite>" + esc(d.author) + "</cite>" +
			"<footer>from " + esc(d.source) + " &middot; added by " + esc(d.contributor) +
			"</footer></blockquote>";

		var json = JSON.stringify(d, null, 2);
		jsonBox.textContent = json;
		preview.hidden = false;

		/* 1. straight into the repo as an issue the maintainer can merge */
		if (repo) {
			actPr.hidden = false;
			actPr.href = "https://github.com/" + repo + "/issues/new?" +
				"title=" + encodeURIComponent("thought: " + d.author + ": " + d.text.slice(0, 50)) +
				"&body=" + encodeURIComponent(
					"Add this to `data/thoughts.json`:\n\n```json\n" + json + "\n```\n\n" +
					(d.source_url ? "Source: " + d.source_url + "\n" : ""));
		} else {
			actPr.hidden = true;
		}

		/* 2. clipboard */
		actCopy.onclick = function (ev) {
			ev.preventDefault();
			var done = function () { note.textContent = "Copied. Paste it into data/thoughts.json and rebuild."; };
			if (navigator.clipboard && navigator.clipboard.writeText) {
				navigator.clipboard.writeText(json).then(done, function () {
					window.getSelection().selectAllChildren(jsonBox);
					note.textContent = "Selected below. Press ⌘C or Ctrl-C.";
				});
			} else {
				window.getSelection().selectAllChildren(jsonBox);
				note.textContent = "Selected below. Press ⌘C or Ctrl-C.";
			}
		};

		/* 3. as a file */
		actDl.onclick = function (ev) {
			ev.preventDefault();
			var blob = new Blob([json], { type: "application/json" }),
				a = document.createElement("a");
			a.href = URL.createObjectURL(blob);
			a.download = "thought-" + (d.author.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "new") + ".json";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
			note.textContent = "Downloaded. Send it on, or drop it into data/thoughts.json yourself.";
		};

		note.textContent = repo ? "" :
			"Tip: set “repo” in data/config.json and a one-click pull-request button appears here too.";
		preview.scrollIntoView({ behavior: "smooth", block: "start" });
	});
})();
