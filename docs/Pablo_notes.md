# Pablo's Notes

These are TODOs to be added, and important directions we should take.

## Notes below
1. Somewhere along the line we broke the "body = 1-line" rule. This CANNOT be broken. The `\n` should never appear in the string. In the Tex compiler, `\par` is what marks a new paragraph. That should be the only necessary way to replace whitespace. Basically the rule is "any >0 number of empty lines in the code gets replaced by 1 instance of `\par`" and otherwise if that rule isn't hit' the rule is "any other whitespace is sent to a single ` `".

2. I wrote a preliminary `order_usepackages.json` describing common non-commutativity between `\usepackage` commands (keys = "a package", values = "packages it modifies and hence needs to be called BEFORE"). In general, we need a study of ALL the things that can't really be removed from the preamble (\newtheoremstyle, \newtheorem, \title, \date, \author,...) without changing pdf output (unless moved to the body, but we shouldnt simply "move our problems to the body", we should only "demacro" the body).

3. We need to expand the arxiv testing pipeline to ALL of arxiv. So far it seems like we're restricting to _DEFAULT_CATEGORIES (from test_fidelity.py) and I think we should aim to sample as close as uniformly on ALL of arxiv's collection of LaTeX papers. Essentially the random arxiv ID generated must be broadened to make sure we're not creating a bias in the tools we're implementing. Final goal = maximal coverage of arxiv, meaning whatever NLP pipeline we want to feed this into should have a maximal cleaned dataset.

4. Commands such as `\geometry{...}` and `\hypersetup{...}` often appear in preamble and are essentially just package options that aren't fed in the usual way as `\usepackage[<usual options>]{...}`. We should standardize this by putting the options back as optional arguments of `\usepackage`. This logic is to be verified before implementing (I'm not 100% sure).

5. We should keep track of our success rate. As we do arxiv tests, we should write how many papers (say in the last 20 we tested) returned a perfectly identical output (extremely short distance: something that wouldn't be true if one command failed to be demacro'ed). The target should be 90%+ success rate. So far we seem quite low.