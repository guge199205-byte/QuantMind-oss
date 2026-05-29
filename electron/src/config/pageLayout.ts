export const PAGE_LAYOUT = {
  outerClass: 'w-full h-full bg-[#f8fafc] p-6 flex flex-col overflow-hidden',
  frameClass: 'bg-white border border-gray-200 shadow-sm w-full h-full rounded-[32px] flex flex-col overflow-hidden',
  headerClass: 'flex-shrink-0 bg-white border-b border-gray-200 px-6 flex items-center justify-between z-10',
  headerHeight: 60,
  sidebarWidth: 240,
  breadcrumbClass: 'px-6 py-3 border-b border-gray-200 bg-gray-50/50',
  contentOuterClass: 'px-6 py-4',
  contentInnerClass: 'max-w-7xl mx-auto h-full',
  scrollContainerClass: 'flex-1 overflow-auto custom-scrollbar',
} as const;
