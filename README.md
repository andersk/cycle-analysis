Usage:

    pip install -r requirements.txt
    pnpm install
    pnpm exec tsc
    cd ../zulip/web/src
    git ls-files '**.ts' '**.js' |
        xargs node ../../../cycle-analysis/graph-imports.js |
        ../../../cycle-analysis/feedback_arc_set.py
