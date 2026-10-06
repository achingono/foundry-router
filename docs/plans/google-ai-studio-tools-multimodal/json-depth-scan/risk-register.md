# Risks

Regex may stallGIL or backtrack onmalformedlongstrings; disjointalternatives and no nestedunbounded
quantifiers plus adversarialbackslash/unclosedstringtimings required. JSONdecoder stillrecursive,
so depthgate must precede it. Invalidstringstructuralcounts may rejectearly but neveracceptbadJSON.
